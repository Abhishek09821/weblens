"""Typography analysis from computed styles and loaded fonts.

Reports: fonts actually loaded, font weights in use, font sizes observed.
Only reports what was measured, never infers from visual similarity.
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

ANALYZER_ID = "design.typography"


class DesignTypographyAnalyzer:
    """Extracts typography information from computed styles."""

    id = ANALYZER_ID
    section = SectionKey.DESIGN
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.STYLES})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        styles = ctx.evidence.styles
        if styles is None:
            return AnalyzerOutput(findings=[])

        findings = []

        # Loaded fonts
        if styles.loaded_fonts:
            unique_fonts = list(dict.fromkeys(styles.loaded_fonts))
            finding = self._build.detected(
                "loaded-fonts",
                category="typography",
                name="Loaded fonts",
                value=len(unique_fonts),
                unit="count",
                values=unique_fonts[:20],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.LOADED_FONT,
                        source="styles.loaded_fonts",
                        excerpt=", ".join(unique_fonts[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Font families from computed styles
        font_families = self._get_values(styles, "font-family")
        if font_families:
            finding = self._build.detected(
                "font-families",
                category="typography",
                name="Font families in use",
                value=len(font_families),
                unit="count",
                values=font_families[:15],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[font-family]",
                        excerpt=", ".join(font_families[:3]),
                    )
                ],
            )
            findings.append(finding)

        # Font weights
        font_weights = self._get_values(styles, "font-weight")
        if font_weights:
            finding = self._build.detected(
                "font-weights",
                category="typography",
                name="Font weights",
                value=len(font_weights),
                unit="count",
                values=font_weights[:10],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[font-weight]",
                        excerpt=", ".join(font_weights[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Font sizes
        font_sizes = self._get_values(styles, "font-size")
        if font_sizes:
            finding = self._build.detected(
                "font-sizes",
                category="typography",
                name="Font sizes",
                value=len(font_sizes),
                unit="count",
                values=font_sizes[:20],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[font-size]",
                        excerpt=", ".join(font_sizes[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Line heights
        line_heights = self._get_values(styles, "line-height")
        if line_heights:
            finding = self._build.detected(
                "line-heights",
                category="typography",
                name="Line heights",
                value=len(line_heights),
                unit="count",
                values=line_heights[:10],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[line-height]",
                        excerpt=", ".join(line_heights[:3]),
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
