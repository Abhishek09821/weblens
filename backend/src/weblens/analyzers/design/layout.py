"""Layout, spacing, and responsive design analysis.

Reports: display types, border-radius values, box shadows, spacing patterns,
responsive viewport behavior. All from computed styles and viewport metrics.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import DesignPayload

ANALYZER_ID = "design.layout"


class DesignLayoutAnalyzer:
    """Extracts layout patterns, spacing, and responsive observations."""

    id = ANALYZER_ID
    section = SectionKey.DESIGN
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.STYLES, EvidenceSlot.VIEWPORTS})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        styles = ctx.evidence.styles
        viewports = ctx.evidence.viewports
        if styles is None:
            return AnalyzerOutput(findings=[])

        findings = []

        # Display values (flex, grid usage)
        displays = self._get_values(styles, "display")
        if displays:
            finding = self._build.detected(
                "display-types",
                category="layout",
                name="Display types",
                value=len(displays),
                unit="count",
                values=displays[:15],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[display]",
                        excerpt=", ".join(displays[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Border radius
        radii = self._get_values(styles, "border-radius")
        if radii:
            finding = self._build.detected(
                "border-radius",
                category="layout",
                name="Border radius values",
                value=len(radii),
                unit="count",
                values=radii[:15],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[border-radius]",
                        excerpt=", ".join(radii[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Box shadows
        shadows = self._get_values(styles, "box-shadow")
        if shadows:
            finding = self._build.detected(
                "box-shadows",
                category="layout",
                name="Box shadow values",
                value=len(shadows),
                unit="count",
                values=shadows[:10],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[box-shadow]",
                        excerpt=shadows[0][:80],
                    )
                ],
            )
            findings.append(finding)

        # Gap (indicates flex/grid gap usage)
        gaps = self._get_values(styles, "gap")
        if gaps:
            finding = self._build.detected(
                "gap-values",
                category="layout",
                name="Gap values (flex/grid)",
                value=len(gaps),
                unit="count",
                values=gaps[:10],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[gap]",
                        excerpt=", ".join(gaps[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Media query breakpoints
        if styles.media_query_breakpoints:
            finding = self._build.detected(
                "breakpoints",
                category="responsive",
                name="Media query breakpoints",
                value=len(styles.media_query_breakpoints),
                unit="count",
                values=styles.media_query_breakpoints[:20],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.media_query_breakpoints",
                        excerpt=", ".join(styles.media_query_breakpoints[:3]),
                    )
                ],
            )
            findings.append(finding)

        # Responsive viewport observations
        if viewports:
            overflow_widths = [vp.width for vp in viewports if vp.has_horizontal_overflow]
            if overflow_widths:
                finding = self._build.detected(
                    "horizontal-overflow",
                    category="responsive",
                    name="Horizontal overflow at viewport widths",
                    value=len(overflow_widths),
                    unit="count",
                    values=[str(w) for w in overflow_widths],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.DOM_MEASUREMENT,
                            source="viewports.has_horizontal_overflow",
                            excerpt=f"Overflow at widths: {overflow_widths}",
                        )
                    ],
                )
                findings.append(finding)

        return AnalyzerOutput(
            findings=findings,
            data=DesignPayload(coverage=styles.coverage) if findings else None,
        )

    def _get_values(self, styles: object, prop_name: str) -> list[str]:
        from weblens.domain.observations import StyleObservation

        assert isinstance(styles, StyleObservation)  # noqa: S101
        for dist in styles.distributions:
            if dist.property == prop_name:
                return [vc.value for vc in dist.values if vc.count >= 2][:20]
        return []
