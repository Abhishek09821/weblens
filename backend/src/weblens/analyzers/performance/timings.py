"""Navigation and paint timing analysis.

Reports: TTFB, FCP, LCP, CLS, long tasks, TBT from one cold lab run.
Always labelled as a single lab measurement, not field data.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import TechnologyPayload

ANALYZER_ID = "performance.timings"

LAB_LIMITATION = (
    "Single cold lab run from one network location. Not representative of real-user "
    "experience. Repeat runs will vary."
)


class PerformanceTimingsAnalyzer:
    """Reports navigation and paint timing metrics."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.PERFORMANCE})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        perf = ctx.evidence.performance
        if perf is None:
            return AnalyzerOutput(findings=[])

        findings = []
        limitations = [LAB_LIMITATION]

        # TTFB
        if perf.ttfb_ms is not None:
            findings.append(
                self._build.detected(
                    "ttfb",
                    category="timing",
                    name="Time to First Byte (TTFB)",
                    value=round(perf.ttfb_ms, 1),
                    unit="ms",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.ttfb_ms",
                            excerpt=f"{perf.ttfb_ms:.1f}ms",
                        )
                    ],
                    limitations=limitations,
                )
            )

        # FCP
        if perf.first_contentful_paint_ms is not None:
            findings.append(
                self._build.detected(
                    "fcp",
                    category="timing",
                    name="First Contentful Paint (FCP)",
                    value=round(perf.first_contentful_paint_ms, 1),
                    unit="ms",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.first_contentful_paint_ms",
                            excerpt=f"{perf.first_contentful_paint_ms:.1f}ms",
                        )
                    ],
                    limitations=limitations,
                )
            )

        # LCP
        if perf.largest_contentful_paint_ms is not None:
            findings.append(
                self._build.detected(
                    "lcp",
                    category="timing",
                    name="Largest Contentful Paint (LCP)",
                    value=round(perf.largest_contentful_paint_ms, 1),
                    unit="ms",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.largest_contentful_paint_ms",
                            excerpt=f"{perf.largest_contentful_paint_ms:.1f}ms"
                            + (
                                f" ({perf.largest_contentful_paint_element})"
                                if perf.largest_contentful_paint_element
                                else ""
                            ),
                        )
                    ],
                    limitations=limitations,
                    details={"element": perf.largest_contentful_paint_element},
                )
            )

        # CLS
        if perf.cumulative_layout_shift is not None:
            findings.append(
                self._build.detected(
                    "cls",
                    category="timing",
                    name="Cumulative Layout Shift (CLS)",
                    value=round(perf.cumulative_layout_shift, 4),
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.cumulative_layout_shift",
                            excerpt=f"{perf.cumulative_layout_shift:.4f}",
                        )
                    ],
                    limitations=limitations,
                )
            )

        # DOMContentLoaded
        if perf.dom_content_loaded_ms is not None:
            findings.append(
                self._build.detected(
                    "dcl",
                    category="timing",
                    name="DOMContentLoaded",
                    value=round(perf.dom_content_loaded_ms, 1),
                    unit="ms",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.dom_content_loaded_ms",
                            excerpt=f"{perf.dom_content_loaded_ms:.1f}ms",
                        )
                    ],
                    limitations=limitations,
                )
            )

        # Load Event
        if perf.load_event_ms is not None:
            findings.append(
                self._build.detected(
                    "load",
                    category="timing",
                    name="Load event",
                    value=round(perf.load_event_ms, 1),
                    unit="ms",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.load_event_ms",
                            excerpt=f"{perf.load_event_ms:.1f}ms",
                        )
                    ],
                    limitations=limitations,
                )
            )

        # TBT
        if perf.total_blocking_estimate_ms is not None:
            findings.append(
                self._build.detected(
                    "tbt",
                    category="timing",
                    name="Total Blocking Time estimate",
                    value=round(perf.total_blocking_estimate_ms, 1),
                    unit="ms",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.PERFORMANCE_ENTRY,
                            source="performance.total_blocking_estimate_ms",
                            excerpt=f"{perf.total_blocking_estimate_ms:.1f}ms "
                            f"({len(perf.long_tasks)} long tasks)",
                        )
                    ],
                    limitations=limitations,
                )
            )

        return AnalyzerOutput(
            findings=findings,
            data=TechnologyPayload(timings=perf) if findings else None,
            limitations=limitations,
        )
