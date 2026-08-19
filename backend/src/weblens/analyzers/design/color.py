"""Design color analysis from computed styles.

Reports: background colors, text colors, accent/brand colors. All derived from
actual computed-style sampling, never guessed from visual appearance.
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

ANALYZER_ID = "design.color"

# Filter out default/transparent/inherit values
_IGNORE_COLORS = frozenset(
    {
        "rgba(0, 0, 0, 0)",
        "transparent",
        "inherit",
        "initial",
        "currentcolor",
        "rgb(0, 0, 0)",
        "rgba(0, 0, 0, 0.0)",
    }
)


class DesignColorAnalyzer:
    """Extracts color palette from computed styles."""

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

        # Extract background colors
        bg_colors = self._extract_property_values(styles, "background-color")
        if bg_colors:
            finding = self._build.detected(
                "background-colors",
                category="color",
                name="Background colors",
                value=len(bg_colors),
                unit="count",
                values=bg_colors[:20],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[background-color]",
                        excerpt=", ".join(bg_colors[:5]),
                    )
                ],
            )
            findings.append(finding)

        # Extract text colors
        text_colors = self._extract_property_values(styles, "color")
        if text_colors:
            finding = self._build.detected(
                "text-colors",
                category="color",
                name="Text colors",
                value=len(text_colors),
                unit="count",
                values=text_colors[:20],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[color]",
                        excerpt=", ".join(text_colors[:5]),
                    )
                ],
            )
            findings.append(finding)

        return AnalyzerOutput(
            findings=findings,
            data=DesignPayload(coverage=styles.coverage) if findings else None,
        )

    def _extract_property_values(self, styles: object, prop_name: str) -> list[str]:
        """Get the top values for a property, filtering out defaults."""
        from weblens.domain.observations import StyleObservation

        assert isinstance(styles, StyleObservation)  # noqa: S101
        for dist in styles.distributions:
            if dist.property == prop_name:
                return [
                    vc.value
                    for vc in dist.values
                    if vc.value.lower() not in _IGNORE_COLORS and vc.count >= 2
                ][:20]
        return []
