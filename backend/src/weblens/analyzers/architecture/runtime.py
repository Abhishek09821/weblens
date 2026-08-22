"""Runtime architecture observations.

Reports: service worker, module vs classic scripts, storage usage,
WebAssembly, console output patterns.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "architecture.runtime"


class ArchitectureRuntimeAnalyzer:
    """Reports runtime architecture observations."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.RUNTIME, EvidenceSlot.NETWORK})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        runtime = ctx.evidence.runtime
        network = ctx.evidence.network

        if runtime is None:
            return AnalyzerOutput(findings=[])

        findings = []

        # Service worker
        if runtime.service_worker_registered:
            findings.append(
                self._build.detected(
                    "service-worker",
                    category="runtime",
                    name="Service Worker",
                    value=True,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.RUNTIME_GLOBAL,
                            source="runtime.service_worker_registered",
                            excerpt="Service worker is registered",
                        )
                    ],
                )
            )

        # Module vs classic scripts
        if runtime.module_script_count is not None or runtime.classic_script_count is not None:
            module = runtime.module_script_count or 0
            classic = runtime.classic_script_count or 0
            if module > 0 or classic > 0:
                findings.append(
                    self._build.detected(
                        "script-types",
                        category="runtime",
                        name="Script module usage",
                        value=f"{module} module, {classic} classic",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.RUNTIME_GLOBAL,
                                source="runtime.script_counts",
                                excerpt=f"{module} ES modules, {classic} classic scripts",
                            )
                        ],
                        details={"module_count": module, "classic_count": classic},
                    )
                )

        # WebAssembly
        if runtime.wasm_requested:
            findings.append(
                self._build.detected(
                    "wasm",
                    category="runtime",
                    name="WebAssembly",
                    value=True,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.RUNTIME_GLOBAL,
                            source="runtime.wasm_requested",
                            excerpt="WebAssembly module requested",
                        )
                    ],
                )
            )

        # Storage usage
        if runtime.storage_keys:
            findings.append(
                self._build.detected(
                    "local-storage",
                    category="runtime",
                    name="LocalStorage keys",
                    value=len(runtime.storage_keys),
                    unit="count",
                    values=runtime.storage_keys[:20],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.RUNTIME_GLOBAL,
                            source="runtime.storage_keys",
                            excerpt=f"{len(runtime.storage_keys)} keys",
                        )
                    ],
                )
            )

        # Console output
        console = ctx.evidence.console
        if console:
            error_count = sum(1 for m in console if m.level in ("error", "warning"))
            if error_count > 0:
                findings.append(
                    self._build.detected(
                        "console-errors",
                        category="runtime",
                        name="Console errors/warnings",
                        value=error_count,
                        unit="count",
                        values=[
                            f"[{m.level}] {m.text[:80]}"
                            for m in console
                            if m.level in ("error", "warning")
                        ][:10],
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.CONSOLE_MESSAGE,
                                source="console",
                                excerpt=f"{error_count} error/warning messages",
                            )
                        ],
                    )
                )

        # API request patterns (XHR/fetch)
        if network:
            api_requests = [r for r in network.requests if r.resource_type in ("xhr", "fetch")]
            if api_requests:
                findings.append(
                    self._build.detected(
                        "api-requests",
                        category="runtime",
                        name="API/XHR requests",
                        value=len(api_requests),
                        unit="count",
                        values=[r.url[:80] for r in api_requests[:10]],
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.NETWORK_REQUEST,
                                source="network.requests[type=xhr|fetch]",
                                excerpt=f"{len(api_requests)} API requests observed",
                            )
                        ],
                    )
                )

        return AnalyzerOutput(findings=findings)
