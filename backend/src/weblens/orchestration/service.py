"""Scan service: admission control, job scheduling, and failure translation.

Sits between the API and the pipeline so routes stay thin and the politeness rules live in one
place. Three admission checks run before a scan is accepted, all configurable:

* a global concurrency cap, because browser work is the scarce resource;
* one scan per host at a time;
* a minimum interval between scans of the same host.

The last two exist because a tool that hammers the sites it analyzes has no business calling
itself polite.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from weblens.ai.inference import InferenceProvider, NullInferenceProvider
from weblens.collection.base import Collector
from weblens.collection.target import NormalizedTarget, TargetGuard
from weblens.config import Settings
from weblens.domain.enums import ScanStatus, SectionKey

if TYPE_CHECKING:
    from weblens.ai.inference import InferenceQuestion
    from weblens.domain.sections import SectionSet
from weblens.domain.errors import (
    NavigationTimeoutError,
    ProblemDetail,
    RateLimitedError,
    ResultExpiredError,
    ScanInProgressError,
    ScanNotFoundError,
    WebLensError,
)
from weblens.domain.scan import (
    AnalysisResult,
    ScanAcceptedResponse,
    ScanJobState,
    ScanRequest,
)
from weblens.logging import get_logger, scan_context
from weblens.orchestration.job_store import InMemoryJobStore, Job
from weblens.orchestration.pipeline import ScanPipeline
from weblens.orchestration.progress import ProgressChannel
from weblens.research.base import NullSearchProvider, SearchProvider
from weblens.utils.ids import new_ulid
from weblens.utils.timing import utc_now

logger = get_logger(__name__)


class ScanService:
    def __init__(
        self,
        settings: Settings,
        store: InMemoryJobStore,
        guard: TargetGuard,
        collector: Collector,
        search_provider: SearchProvider | None = None,
        inference_provider: InferenceProvider | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._guard = guard
        self._pipeline = ScanPipeline(
            settings,
            collector,
            search_provider=search_provider or NullSearchProvider(),
            inference_provider=inference_provider or NullInferenceProvider(),
        )
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_scans)

    # --- commands ----------------------------------------------------------------------

    async def submit(self, request: ScanRequest) -> ScanAcceptedResponse:
        """Validate, admit, and schedule a scan. Raises on rejection."""
        target = await self._guard.prepare(request.url)
        await self._admit(target)

        scan_id = new_ulid()
        channel = ProgressChannel(scan_id=scan_id, requested_url=target.requested_url)
        job = Job(
            scan_id=scan_id,
            requested_url=target.requested_url,
            normalized_url=target.display_url,
            host=target.host,
            options=request.options,
            channel=channel,
        )
        await self._store.create(job)
        job.task = asyncio.create_task(self._execute(job, target), name=f"weblens-scan-{scan_id}")

        logger.info("scan accepted", extra={"scan_id": scan_id, "host": target.host})
        return ScanAcceptedResponse(
            scan_id=scan_id,
            status=ScanStatus.QUEUED,
            requested_url=target.requested_url,
            normalized_url=target.display_url,
            created_at=job.created_at,
            links={
                "self": f"/api/v1/scans/{scan_id}",
                "events": f"/api/v1/scans/{scan_id}/events",
                "result": f"/api/v1/scans/{scan_id}/result",
            },
        )

    async def delete(self, scan_id: str) -> None:
        """Release the server-side copy. Idempotent: the desired end state is 'gone'."""
        job = await self._store.get(scan_id)
        if job is not None and job.task is not None and not job.task.done():
            job.task.cancel()
        await self._store.delete(scan_id)

    # --- queries -----------------------------------------------------------------------

    async def job_state(self, scan_id: str) -> ScanJobState:
        job = await self._require(scan_id)
        return job.channel.snapshot()

    async def result(self, scan_id: str) -> AnalysisResult:
        job = await self._require(scan_id)
        if job.result is not None:
            return job.result
        if job.channel.status.is_terminal:
            # Terminal without a result means the scan failed before assembly.
            raise ResultExpiredError(
                "The scan finished without producing a result. See the job state for the error."
            )
        raise ScanInProgressError(f"Scan {scan_id} is {job.channel.status.value}.")

    async def channel(self, scan_id: str) -> ProgressChannel:
        job = await self._require(scan_id)
        return job.channel

    async def _require(self, scan_id: str) -> Job:
        job = await self._store.get(scan_id)
        if job is None:
            raise ScanNotFoundError(
                f"No scan with id {scan_id} is buffered. Results are released once stored by "
                "the client, so this id may simply have been cleaned up."
            )
        return job

    # --- AI intelligence fallback -------------------------------------------------------

    async def run_intelligence(
        self,
        scan_id: str,
        sections: list[SectionKey],
        additional_context: str | None = None,
    ) -> tuple[AnalysisResult, int]:
        """Run AI intelligence fallback on an existing scan result.

        Returns the enhanced result and the number of findings added.
        AI findings are appended to the relevant sections with status=AI_INFERRED.
        Existing deterministic findings are never modified.
        """
        from weblens.ai.inference import claims_to_findings
        from weblens.domain.quality import assess_quality

        job = await self._require(scan_id)
        if job.result is None:
            raise ScanInProgressError(f"Scan {scan_id} has not produced a result yet.")

        result = job.result
        sections_set = result.sections

        # Build inference questions for requested sections
        questions = self._build_intelligence_questions(sections_set, sections, additional_context)

        # Build evidence summary
        evidence_summary = self._build_intelligence_summary(result, additional_context)

        # Run research if available (re-uses existing research if present in evidence)
        research = None
        if hasattr(self._pipeline, "_search_provider"):
            from weblens.research.base import execute_research

            provider = self._pipeline._search_provider
            if provider.is_available:
                # Build dynamic queries from evidence
                hints = self._extract_research_hints(result)
                research = await execute_research(provider, result.target.host, hints)

        # Run inference
        inference_provider = self._pipeline._inference_provider
        if inference_provider.is_available:
            inference_results = await inference_provider.infer(
                questions, evidence_summary, research
            )
            new_findings = claims_to_findings(inference_results)
        else:
            new_findings = []

        # Merge AI findings into the appropriate sections
        findings_added = 0
        updated_sections = sections_set.model_dump()

        for finding in new_findings:
            # Determine target section from the question id
            target_section = self._finding_target_section(finding, sections)
            section_data = updated_sections[target_section.value]
            section_data["findings"].append(finding.model_dump())
            findings_added += 1

        # Rebuild sections model
        from weblens.domain.sections import SectionSet

        new_sections = SectionSet.model_validate(updated_sections)

        # Reassess quality
        new_quality = assess_quality(new_sections)

        # Update the stored result
        enhanced_result = result.model_copy(
            update={
                "sections": new_sections,
                "quality": new_quality,
            }
        )
        await self._store.set_result(scan_id, enhanced_result)

        return enhanced_result, findings_added

    def _build_intelligence_questions(
        self,
        sections: SectionSet,
        target_sections: list[SectionKey],
        additional_context: str | None,
    ) -> list[InferenceQuestion]:
        """Build structured questions for the AI based on what needs enhancement.

        Questions are designed to produce evidence-backed verdicts that clearly distinguish
        observable facts from hypotheses. Each section gets targeted questions that correspond
        to the spec's four-report structure.
        """
        from weblens.ai.inference import InferenceQuestion

        questions: list[InferenceQuestion] = []
        tech_findings = sections.technology.findings
        detected_tech = [f.name for f in tech_findings if f.is_asserted]
        context_suffix = f"\nAdditional context: {additional_context}" if additional_context else ""

        if SectionKey.TECHNOLOGY in target_sections:
            tech_context = f"Detected technologies: {', '.join(detected_tech[:20])}{context_suffix}"
            questions.extend([
                InferenceQuestion(
                    id="tech:frontend_framework",
                    question="Based on all observable evidence (DOM structure, JavaScript "
                    "patterns, hydration signals, runtime globals, script URLs), what "
                    "frontend framework or rendering system is this website most likely using? "
                    "Consider: React, Vue, Angular, Svelte, "
                    "Next.js, Nuxt, Astro, custom/proprietary.",
                    context=tech_context,
                    section="technology",
                ),
                InferenceQuestion(
                    id="tech:backend_technology",
                    question="Based on observable evidence (HTTP headers, API response patterns, "
                    "URL structures, cookie naming, error page signatures), what backend "
                    "technology or server-side framework is most likely in use? "
                    "If the backend technology is not publicly determinable from external "
                    "observation, state that clearly with verdict 'not_publicly_determinable'.",
                    context=tech_context,
                    section="technology",
                ),
                InferenceQuestion(
                    id="tech:architecture_pattern",
                    question="What architecture patterns are supported by the evidence? "
                    "Consider: SSR vs CSR vs SSG, microservices vs monolith, JAMstack, "
                    "serverless, edge-rendered. What is the rendering model?",
                    context=tech_context,
                    section="technology",
                ),
                InferenceQuestion(
                    id="tech:data_layer",
                    question="Is there any publicly observable evidence of the database, "
                    "cache (Redis/Memcached), message queue, or data layer technology? "
                    "If not determinable from public observation, verdict must be "
                    "'not_publicly_determinable'. Never fabricate database claims.",
                    context=tech_context,
                    section="technology",
                ),
                InferenceQuestion(
                    id="tech:build_tooling",
                    question="Based on script bundle patterns, source map references, "
                    "module format, and chunk naming conventions, what build tooling "
                    "is likely in use? Consider: webpack, Vite, esbuild, Turbopack, Parcel.",
                    context=tech_context,
                    section="technology",
                ),
                InferenceQuestion(
                    id="tech:authentication",
                    question="Based on cookies, headers, redirect patterns, and API endpoints, "
                    "what authentication mechanism or provider might be in use? "
                    "Consider: OAuth, JWT, session-based, SSO providers.",
                    context=tech_context,
                    section="technology",
                ),
            ])

        if SectionKey.DESIGN in target_sections:
            design_findings = sections.design.findings
            design_obs = [f.name for f in design_findings if f.is_asserted][:20]
            design_context = f"Design observations: {', '.join(design_obs)}{context_suffix}"
            questions.extend([
                InferenceQuestion(
                    id="design:system",
                    question="Based on the observable design evidence (typography, colors, "
                    "spacing, component patterns, layout system), what design system or "
                    "component library might this website be using? Consider: Material Design, "
                    "Ant Design, Tailwind components, custom/proprietary design system.",
                    context=design_context,
                    section="design",
                ),
                InferenceQuestion(
                    id="design:component_structure",
                    question="Based on DOM structure, CSS class naming patterns, and repeated "
                    "UI patterns, what is the likely component architecture? Describe the "
                    "page hierarchy: header/nav, hero, content sections, cards/grids, footer.",
                    context=design_context,
                    section="design",
                ),
                InferenceQuestion(
                    id="design:responsive_strategy",
                    question="Based on observed breakpoints, viewport behavior, and CSS patterns, "
                    "what is the responsive design strategy? Mobile-first? Desktop-first? "
                    "What layout patterns are used (flex, grid, responsive containers)?",
                    context=design_context,
                    section="design",
                ),
            ])

        if SectionKey.SECURITY in target_sections:
            security_findings = sections.security.findings
            security_obs = [f.name for f in security_findings if f.is_asserted][:20]
            security_context = f"Security observations: {', '.join(security_obs)}{context_suffix}"
            questions.extend([
                InferenceQuestion(
                    id="security:posture_assessment",
                    question="Based on the observable security evidence (headers, TLS, cookies, "
                    "CSP, CORS, mixed content), provide an overall security posture assessment. "
                    "What are the notable strengths and observable gaps? "
                    "IMPORTANT: This is an externally observable assessment only. "
                    "You cannot claim the site is secure or insecure "
                    "— only describe what is observable.",
                    context=security_context,
                    section="security",
                ),
                InferenceQuestion(
                    id="security:third_party_risk",
                    question="Based on third-party scripts, external resources, and cross-origin "
                    "requests observed, what is the third-party security exposure? "
                    "Are there notable concentrations of external dependencies?",
                    context=security_context,
                    section="security",
                ),
            ])

        if SectionKey.TRAFFIC in target_sections:
            traffic_context = f"Target domain analysis{context_suffix}"
            questions.extend([
                InferenceQuestion(
                    id="traffic:popularity_estimate",
                    question="Based on public information and publicly available ranking data, "
                    "what is the likely popularity band for this website? "
                    "Only cite verifiable public sources. If no credible source exists, "
                    "verdict must be 'unable_to_verify'. Never fabricate exact traffic numbers.",
                    context=traffic_context,
                    section="traffic",
                ),
                InferenceQuestion(
                    id="traffic:market_position",
                    question="Based on the detected analytics services, third-party integrations, "
                    "and overall site sophistication, what market segment does this website "
                    "likely serve? Enterprise, mid-market, small business, consumer?",
                    context=traffic_context,
                    section="traffic",
                ),
            ])

        return questions

    @staticmethod
    def _build_intelligence_summary(
        result: AnalysisResult,
        additional_context: str | None,
    ) -> dict[str, object]:
        """Build condensed evidence summary for the AI intelligence pipeline."""
        sections = result.sections
        summary: dict[str, object] = {
            "host": result.target.host,
            "url": result.target.normalized_url,
            "http_status": result.target.http_status,
            "document_title": result.target.document_title,
            "technology_findings": [
                {"id": f.id, "name": f.name, "status": f.status.value, "value": f.value}
                for f in sections.technology.findings
                if f.is_asserted
            ],
            "design_findings": [
                {"id": f.id, "name": f.name, "category": f.category}
                for f in sections.design.findings
                if f.is_asserted
            ][:30],
            "security_findings": [
                {"id": f.id, "name": f.name, "status": f.status.value}
                for f in sections.security.findings
            ][:30],
            "traffic_findings": [
                {"id": f.id, "name": f.name, "status": f.status.value, "value": f.value}
                for f in sections.traffic.findings
            ],
        }
        if additional_context:
            summary["user_provided_context"] = additional_context
        return summary

    @staticmethod
    def _extract_research_hints(result: AnalysisResult) -> list[str]:
        """Extract technology hints from deterministic findings for dynamic research queries."""
        hints: list[str] = []
        for finding in result.sections.technology.findings:
            if finding.is_asserted and finding.detected:
                name = finding.name
                if name and name not in hints:
                    hints.append(name)
        return hints[:5]

    @staticmethod
    def _finding_target_section(finding: object, target_sections: list[SectionKey]) -> SectionKey:
        """Determine which section an AI finding belongs to based on its source question.

        Question IDs use the pattern 'section:topic' (e.g. 'tech:frontend_framework').
        The finding ID carries the question ID, so we can route accurately.
        """
        from weblens.domain.findings import Finding

        if isinstance(finding, Finding):
            fid = finding.id
            # Route based on the question ID prefix in the finding ID
            if "design:" in fid or "design_" in fid:
                return SectionKey.DESIGN
            if "security:" in fid or "security_" in fid:
                return SectionKey.SECURITY
            if "traffic:" in fid or "traffic_" in fid:
                return SectionKey.TRAFFIC
            if "tech:" in fid or "technology" in fid:
                return SectionKey.TECHNOLOGY
        # Default to technology for unrecognized patterns
        return SectionKey.TECHNOLOGY

    # --- execution ---------------------------------------------------------------------

    async def _admit(self, target: NormalizedTarget) -> None:
        active = await self._store.active_count()
        if active >= self._settings.max_concurrent_scans:
            raise RateLimitedError(
                f"{active} scans are already running "
                f"(limit {self._settings.max_concurrent_scans}). Try again shortly.",
                retry_after_seconds=10,
            )

        running_for_host, last_seen = await self._store.host_activity(target.host)
        if running_for_host >= self._settings.max_concurrent_scans_per_host:
            raise RateLimitedError(
                f"A scan of {target.host} is already running. WebLens runs one scan per host at "
                "a time to avoid load on the target.",
                retry_after_seconds=15,
            )
        if last_seen is not None:
            elapsed = (utc_now() - last_seen).total_seconds()
            interval = self._settings.min_host_interval_seconds
            if elapsed < interval:
                wait = int(interval - elapsed) + 1
                raise RateLimitedError(
                    f"{target.host} was scanned {int(elapsed)}s ago. WebLens spaces scans of the "
                    f"same host by {int(interval)}s.",
                    retry_after_seconds=wait,
                )

    async def _execute(self, job: Job, target: NormalizedTarget) -> None:
        with scan_context(job.scan_id):
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(
                        self._pipeline.run(job, target),
                        timeout=self._settings.total_scan_budget_seconds,
                    )
            except asyncio.CancelledError:
                await job.channel.mark_finished(ScanStatus.CANCELLED)
                raise
            except TimeoutError:
                budget_error = NavigationTimeoutError(
                    f"The scan exceeded its {self._settings.total_scan_budget_ms} ms budget."
                )
                await job.channel.mark_failed(ProblemDetail.from_error(budget_error))
                logger.warning("scan exceeded budget")
                return
            except WebLensError as error:
                await job.channel.mark_failed(ProblemDetail.from_error(error))
                logger.info("scan failed", extra={"code": error.code.value, "detail": error.detail})
                return
            except Exception:
                logger.exception("scan crashed")
                await job.channel.mark_failed(
                    ProblemDetail.from_error(
                        WebLensError("An unexpected error ended the scan. The incident was logged.")
                    )
                )
                return

            await self._store.set_result(job.scan_id, result)
            await job.channel.mark_finished(result.scan.status)
            logger.info(
                "scan finished",
                extra={
                    "status": result.scan.status.value,
                    "duration_ms": result.scan.duration_ms,
                    "errors": len(result.errors),
                },
            )
