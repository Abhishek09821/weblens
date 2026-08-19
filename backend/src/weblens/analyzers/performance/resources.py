"""Resource analysis: bytes, counts, type breakdown, compression.

Reports: total resources, transfer size, resource type distribution,
render-blocking resources. From the network observation.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "performance.resources"


class PerformanceResourcesAnalyzer:
    """Resource count and size analysis from network observations."""

    id = ANALYZER_ID
    section = SectionKey.PERFORMANCE
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.NETWORK})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        network = ctx.evidence.network
        if network is None:
            return AnalyzerOutput(findings=[])

        findings = []
        requests = network.requests

        # Total request count
        total = len(requests)
        if total > 0:
            findings.append(
                self._build.detected(
                    "request-count",
                    category="resources",
                    name="Total network requests",
                    value=total,
                    unit="count",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.NETWORK_REQUEST,
                            source="network.requests",
                            excerpt=f"{total} requests recorded"
                            + (" (cap reached)" if network.cap_hit else ""),
                        )
                    ],
                )
            )

        # Resource type breakdown
        type_counts: dict[str, int] = {}
        for req in requests:
            rt = req.resource_type or "other"
            type_counts[rt] = type_counts.get(rt, 0) + 1

        if type_counts:
            sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
            findings.append(
                self._build.detected(
                    "resource-types",
                    category="resources",
                    name="Resource type breakdown",
                    value=len(type_counts),
                    unit="count",
                    values=[f"{rt}: {count}" for rt, count in sorted_types[:15]],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.NETWORK_REQUEST,
                            source="network.requests.resource_type",
                            excerpt=", ".join(f"{rt}={c}" for rt, c in sorted_types[:5]),
                        )
                    ],
                )
            )

        # Transfer size (from performance observation if available)
        perf = ctx.evidence.performance
        if perf and perf.transfer_bytes_total:
            kb = round(perf.transfer_bytes_total / 1024, 1)
            findings.append(
                self._build.detected(
                    "transfer-size",
                    category="resources",
                    name="Total transfer size",
                    value=perf.transfer_bytes_total,
                    unit="bytes",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.transfer_bytes_total",
                            excerpt=f"{kb} KB transferred",
                        )
                    ],
                    details={"kb": kb},
                )
            )

        # Failed requests
        failed = [req for req in requests if req.failed]
        if failed:
            findings.append(
                self._build.detected(
                    "failed-requests",
                    category="resources",
                    name="Failed resource requests",
                    value=len(failed),
                    unit="count",
                    values=[req.url[:100] for req in failed[:10]],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.NETWORK_REQUEST,
                            source="network.requests[failed=true]",
                            excerpt=f"{len(failed)} failed requests",
                        )
                    ],
                )
            )

        return AnalyzerOutput(findings=findings)
