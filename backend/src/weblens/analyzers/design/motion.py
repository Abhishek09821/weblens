"""Animation and transition analysis.

Reports: transition and animation usage counts, keyframe definitions, animation libraries.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "design.motion"


class DesignMotionAnalyzer:
    """Analyzes animation and transition usage from computed styles."""

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

        # Transitions
        transitions = self._get_values(styles, "transition")
        if transitions:
            finding = self._build.detected(
                "transitions",
                category="motion",
                name="CSS transitions",
                value=len(transitions),
                unit="count",
                values=transitions[:10],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[transition]",
                        excerpt=transitions[0][:80],
                    )
                ],
            )
            findings.append(finding)

        # Animations
        animations = self._get_values(styles, "animation")
        if animations:
            finding = self._build.detected(
                "animations",
                category="motion",
                name="CSS animations",
                value=len(animations),
                unit="count",
                values=animations[:10],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.distributions[animation]",
                        excerpt=animations[0][:80],
                    )
                ],
            )
            findings.append(finding)

        # Keyframe count
        if styles.keyframe_count and styles.keyframe_count > 0:
            finding = self._build.detected(
                "keyframes",
                category="motion",
                name="CSS keyframe definitions",
                value=styles.keyframe_count,
                unit="count",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COMPUTED_STYLE,
                        source="styles.keyframe_count",
                        excerpt=f"{styles.keyframe_count} @keyframes rules",
                    )
                ],
            )
            findings.append(finding)

        return AnalyzerOutput(findings=findings)

    def _get_values(self, styles: object, prop_name: str) -> list[str]:
        from weblens.domain.observations import StyleObservation

        assert isinstance(styles, StyleObservation)  # noqa: S101
        for dist in styles.distributions:
            if dist.property == prop_name:
                return [vc.value for vc in dist.values if vc.count >= 1][:20]
        return []
