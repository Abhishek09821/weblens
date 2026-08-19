"""Scan pipeline.

Sequences collection, runs analyzers in isolation, and assembles the result. The isolation is
the important part: an analyzer that raises, times out, or lacks evidence degrades its own
section and nothing else (axiom A7). A scan only fails outright when collection cannot produce
a document at all.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from weblens.analyzers.base import Analyzer, AnalyzerContext, AnalyzerOutput
from weblens.collection.base import Collector
from weblens.collection.target import NormalizedTarget
from weblens.config import Settings
from weblens.domain.enums import (
    AnalyzerRunStatus,
    ErrorCode,
    ScanStatus,
    SectionKey,
    SectionStatus,
    StageKey,
)
from weblens.domain.errors import ScanError
from weblens.domain.evidence import RawEvidence
from weblens.domain.findings import Finding, Interpretation
from weblens.domain.scan import (
    AnalysisResult,
    RedirectHop,
    RunContext,
    ScanMetadata,
    ScanOptions,
    ScreenshotRef,
    TargetInfo,
)
from weblens.domain.sections import (
    AccessibilityPayload,
    AnalyzerRun,
    ArchitecturePayload,
    DesignPayload,
    NetworkPayload,
    PerformancePayload,
    Section,
    SectionMeta,
    SectionSet,
    SecurityPayload,
    SeoPayload,
    TechnologyPayload,
)
from weblens.logging import get_logger, stage_context
from weblens.orchestration import registry
from weblens.orchestration.job_store import Job
from weblens.orchestration.progress import ProgressChannel
from weblens.orchestration.registry import AnalyzerEntry
from weblens.utils.timing import Stopwatch, utc_now

logger = get_logger(__name__)

SCAN_LIMITATIONS = [
    "One URL was analyzed. No crawling was performed, so findings describe this page only.",
    "A single run at one point in time from one network location. Repeat runs will differ.",
    "Passive observation only: no forms were submitted, no authentication was attempted, and "
    "no access controls were tested.",
]

_PAYLOAD_TYPES: dict[SectionKey, type] = {
    SectionKey.DESIGN: DesignPayload,
    SectionKey.TECHNOLOGY: TechnologyPayload,
    SectionKey.SECURITY: SecurityPayload,
    SectionKey.PERFORMANCE: PerformancePayload,
    SectionKey.ACCESSIBILITY: AccessibilityPayload,
    SectionKey.SEO: SeoPayload,
    SectionKey.ARCHITECTURE: ArchitecturePayload,
    SectionKey.NETWORK: NetworkPayload,
}


@dataclass
class _SectionAccumulator:
    findings: list[Finding]
    interpretations: list[Interpretation]
    runs: list[AnalyzerRun]
    limitations: list[str]
    data: object | None = None

    @classmethod
    def empty(cls) -> _SectionAccumulator:
        return cls(findings=[], interpretations=[], runs=[], limitations=[])


class ScanPipeline:
    def __init__(self, settings: Settings, collector: Collector) -> None:
        self._settings = settings
        self._collector = collector

    async def run(self, job: Job, target: NormalizedTarget) -> AnalysisResult:
        """Execute the pipeline. Collection failures raise; analyzer failures are recorded."""
        channel = job.channel
        errors: list[ScanError] = []
        watch = Stopwatch()

        await channel.mark_running()
        await channel.stage_started(StageKey.VALIDATE)
        await channel.stage_completed(StageKey.VALIDATE)

        outcome = await self._collector.collect(target, job.options, channel)
        evidence = outcome.evidence

        sections, analyzer_errors = await self._analyze(evidence, job.options, channel)
        errors.extend(analyzer_errors)

        with stage_context(StageKey.ASSEMBLE.value):
            await channel.finalize_pending(
                f"Not run by the {self._collector.collection_mode} collector.",
                exclude=(StageKey.ASSEMBLE,),
            )
            await channel.stage_started(StageKey.ASSEMBLE)
            status = (
                ScanStatus.COMPLETED_WITH_ERRORS
                if errors or _any_section_degraded(sections)
                else ScanStatus.COMPLETED
            )
            # Close the stage before snapshotting the stage list: the remaining work is building
            # the envelope below, and a result that reports its own assemble stage as still
            # "running" forever would be a permanent lie in stored data.
            await channel.stage_completed(StageKey.ASSEMBLE)
            result = AnalysisResult(
                scan=ScanMetadata(
                    scan_id=job.scan_id,
                    status=status,
                    created_at=job.created_at,
                    started_at=channel.started_at,
                    finished_at=utc_now(),
                    duration_ms=watch.elapsed_ms(),
                    options=job.options,
                    run_context=outcome.run_context,
                    stages=channel.stage_runs(),
                ),
                target=self._target_info(target, evidence, outcome.redirect_chain),
                sections=sections,
                errors=errors,
                screenshots=self._screenshots(evidence),
                limitations=[*SCAN_LIMITATIONS, *_collection_mode_limitations(outcome.run_context)],
            )
        return result

    # --- analysis ----------------------------------------------------------------------

    async def _analyze(
        self, evidence: RawEvidence, options: ScanOptions, channel: ProgressChannel
    ) -> tuple[SectionSet, list[ScanError]]:
        errors: list[ScanError] = []
        accumulators: dict[SectionKey, _SectionAccumulator] = {
            key: _SectionAccumulator.empty() for key in SectionKey
        }
        produced: dict[str, Finding] = {}
        requested = set(options.sections) if options.sections else set(SectionKey)

        with stage_context(StageKey.ANALYZE.value):
            await channel.stage_started(StageKey.ANALYZE)
            for entry in registry.implemented_entries():
                if entry.section not in requested:
                    continue
                run, output = await self._run_analyzer(entry, evidence, produced)
                accumulator = accumulators[entry.section]
                accumulator.runs.append(run)

                if output is not None:
                    accumulator.findings.extend(output.findings)
                    accumulator.interpretations.extend(output.interpretations)
                    accumulator.limitations.extend(output.limitations)
                    if output.data is not None:
                        accumulator.data = output.data
                    for finding in output.findings:
                        produced[finding.id] = finding

                if run.status in (AnalyzerRunStatus.FAILED, AnalyzerRunStatus.TIMEOUT):
                    errors.append(
                        ScanError(
                            code=run.error_code or ErrorCode.ANALYZER_FAILED,
                            scope="analyzer",
                            subject=entry.id,
                            message=f"Analyzer '{entry.id}' did not complete.",
                            detail=run.error_detail,
                        )
                    )
            await channel.stage_completed(StageKey.ANALYZE)

        return self._build_sections(accumulators, requested), errors

    async def _run_analyzer(
        self,
        entry: AnalyzerEntry,
        evidence: RawEvidence,
        produced: dict[str, Finding],
    ) -> tuple[AnalyzerRun, AnalyzerOutput | None]:
        missing = evidence.missing(entry.requires)
        if missing:
            return (
                AnalyzerRun(
                    id=entry.id,
                    version=entry.version,
                    status=AnalyzerRunStatus.SKIPPED,
                    error_code=ErrorCode.MISSING_EVIDENCE,
                    error_detail="Required evidence was not collected.",
                    missing_evidence=[slot.value for slot in missing],
                ),
                None,
            )

        if entry.factory is None:  # pragma: no cover - implemented_entries() filters these out
            raise RuntimeError(f"analyzer {entry.id} was scheduled without an implementation")
        analyzer: Analyzer = entry.factory()
        ctx = AnalyzerContext(evidence=evidence, findings=dict(produced))
        watch = Stopwatch()
        timeout = self._settings.analyzer_timeout_ms / 1000

        try:
            # Analyzers are synchronous and pure; running them in a worker thread keeps a
            # pathological one from blocking the event loop, and gives us a timeout seam.
            output = await asyncio.wait_for(asyncio.to_thread(analyzer.analyze, ctx), timeout)
        except TimeoutError:
            logger.warning("analyzer timed out", extra={"analyzer": entry.id})
            return (
                AnalyzerRun(
                    id=entry.id,
                    version=entry.version,
                    status=AnalyzerRunStatus.TIMEOUT,
                    duration_ms=watch.elapsed_ms(),
                    error_code=ErrorCode.ANALYZER_TIMEOUT,
                    error_detail=f"Exceeded {self._settings.analyzer_timeout_ms} ms.",
                ),
                None,
            )
        except Exception as exc:
            logger.warning(
                "analyzer failed", extra={"analyzer": entry.id, "error": type(exc).__name__}
            )
            return (
                AnalyzerRun(
                    id=entry.id,
                    version=entry.version,
                    status=AnalyzerRunStatus.FAILED,
                    duration_ms=watch.elapsed_ms(),
                    error_code=ErrorCode.ANALYZER_FAILED,
                    error_detail=f"{type(exc).__name__}: {exc}"[:500],
                ),
                None,
            )

        return (
            AnalyzerRun(
                id=entry.id,
                version=entry.version,
                status=AnalyzerRunStatus.COMPLETED,
                duration_ms=watch.elapsed_ms(),
            ),
            output,
        )

    # --- assembly ----------------------------------------------------------------------

    def _build_sections(
        self,
        accumulators: dict[SectionKey, _SectionAccumulator],
        requested: set[SectionKey],
    ) -> SectionSet:
        return SectionSet(
            design=self._build_section(SectionKey.DESIGN, accumulators, requested),
            technology=self._build_section(SectionKey.TECHNOLOGY, accumulators, requested),
            security=self._build_section(SectionKey.SECURITY, accumulators, requested),
            performance=self._build_section(SectionKey.PERFORMANCE, accumulators, requested),
            accessibility=self._build_section(SectionKey.ACCESSIBILITY, accumulators, requested),
            seo=self._build_section(SectionKey.SEO, accumulators, requested),
            architecture=self._build_section(SectionKey.ARCHITECTURE, accumulators, requested),
            network=self._build_section(SectionKey.NETWORK, accumulators, requested),
        )

    def _build_section(
        self,
        key: SectionKey,
        accumulators: dict[SectionKey, _SectionAccumulator],
        requested: set[SectionKey],
    ) -> Any:
        """Build the section with the payload type declared for it.

        The parametrized class is resolved at runtime from ``_PAYLOAD_TYPES`` so this stays one
        method instead of eight near-identical ones. ``SectionSet`` then validates that the
        payload an analyzer produced actually matches the type its section declares - a
        mismatch is a programming error and surfaces immediately.
        """
        accumulator = accumulators[key]
        status, reason = self._section_status(key, accumulator, requested)
        meta = SectionMeta(
            key=key,
            status=status,
            analyzers=self._section_runs(key, accumulator),
            limitations=_dedupe(accumulator.limitations),
            unavailable_reason=reason,
        )
        payload_type = _PAYLOAD_TYPES[key]
        section_type: Any = Section[payload_type]  # type: ignore[valid-type]
        return section_type(
            meta=meta,
            findings=accumulator.findings,
            interpretations=accumulator.interpretations,
            data=accumulator.data,
        )

    def _section_runs(self, key: SectionKey, accumulator: _SectionAccumulator) -> list[AnalyzerRun]:
        """Every analyzer declared for the section, including unimplemented ones.

        A reader can then see not just what ran, but what exists and did not run - which is
        the difference between "this site has no framework signals" and "we have not built
        framework detection yet".
        """
        reported = {run.id for run in accumulator.runs}
        runs = list(accumulator.runs)
        for entry in registry.entries_for_section(key):
            if entry.id in reported:
                continue
            if entry.implemented:
                continue
            runs.append(
                AnalyzerRun(
                    id=entry.id,
                    version=entry.version,
                    status=AnalyzerRunStatus.NOT_IMPLEMENTED,
                    error_detail=f"Planned for phase {entry.phase}.",
                )
            )
        return runs

    def _section_status(
        self,
        key: SectionKey,
        accumulator: _SectionAccumulator,
        requested: set[SectionKey],
    ) -> tuple[SectionStatus, str | None]:
        if key not in requested:
            return SectionStatus.SKIPPED, "This section was excluded from the scan request."
        if not registry.section_has_implementation(key):
            planned = ", ".join(entry.id for entry in registry.entries_for_section(key))
            return (
                SectionStatus.NOT_IMPLEMENTED,
                f"No analyzer for this section ships in this build yet. Planned: {planned}.",
            )

        completed = [run for run in accumulator.runs if run.status is AnalyzerRunStatus.COMPLETED]
        attempted = accumulator.runs
        if not attempted:
            return SectionStatus.UNAVAILABLE, "No analyzer for this section was scheduled."
        if not completed:
            detail = "; ".join(
                f"{run.id}: {run.error_detail or run.status.value}" for run in attempted
            )
            return SectionStatus.UNAVAILABLE, f"Every analyzer for this section failed. {detail}"
        if len(completed) < len(attempted):
            failed = ", ".join(run.id for run in attempted if run not in completed)
            return SectionStatus.PARTIAL, f"Some analyzers did not complete: {failed}."
        if len(completed) < len(
            [entry for entry in registry.entries_for_section(key) if entry.implemented]
        ):
            return SectionStatus.PARTIAL, "Not every available analyzer contributed."
        return SectionStatus.COMPLETE, None

    def _target_info(
        self, target: NormalizedTarget, evidence: RawEvidence, redirect_chain: list[RedirectHop]
    ) -> TargetInfo:
        return TargetInfo(
            requested_url=target.requested_url,
            normalized_url=target.display_url,
            final_url=evidence.http.final_url if evidence.http else None,
            host=target.host,
            port=target.port,
            scheme=target.scheme,
            resolved_ips=list(target.resolved_ips),
            redirect_chain=redirect_chain,
            http_status=evidence.http.status if evidence.http else None,
            document_title=evidence.dom.title if evidence.dom else None,
            robots=evidence.robots,
        )

    @staticmethod
    def _screenshots(evidence: RawEvidence) -> list[ScreenshotRef]:
        if not evidence.screenshots:
            return []
        return [
            ScreenshotRef(
                label=shot.label,
                width=shot.width,
                height=shot.height,
                mime_type=shot.mime_type,
                data_base64=shot.data_base64,
            )
            for shot in evidence.screenshots
        ]


def _any_section_degraded(sections: SectionSet) -> bool:
    return any(
        getattr(sections, key.value).meta.status
        in (SectionStatus.PARTIAL, SectionStatus.UNAVAILABLE)
        for key in SectionKey
    )


def _collection_mode_limitations(run_context: RunContext) -> list[str]:
    if run_context.collection_mode == "http_only":
        return [
            "This scan used HTTP collection only: no browser was used, so the rendered DOM, "
            "computed styles, performance entries, and accessibility rules were not observed.",
        ]
    return []


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
