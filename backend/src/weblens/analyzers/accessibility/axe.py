"""axe-core results analysis.

Reports: violations grouped by impact, passes count, rule coverage.
Does not produce a score - violation counts are not a conformance measure.
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

ANALYZER_ID = "accessibility.axe"

COVERAGE_NOTE = (
    "Automated rules detect a subset of WCAG issues. A clean result does not mean a site "
    "is accessible; conformance requires manual testing and expert review."
)


class AccessibilityAxeAnalyzer:
    """Reports axe-core accessibility violations."""

    id = ANALYZER_ID
    section = SectionKey.DESIGN
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.ACCESSIBILITY})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        axe = ctx.evidence.accessibility
        if axe is None:
            return AnalyzerOutput(findings=[])

        findings = []
        limitations = [COVERAGE_NOTE]

        if axe.error:
            findings.append(
                self._build.detected(
                    "execution-error",
                    category="automated-testing",
                    name="axe-core execution error",
                    value=axe.error,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.AXE_RESULT,
                            source="accessibility.error",
                            excerpt=axe.error[:200],
                        )
                    ],
                )
            )
            return AnalyzerOutput(findings=findings, limitations=limitations)

        # Summary
        total_violations = len(axe.violations)
        total_nodes = sum(v.node_count for v in axe.violations)

        findings.append(
            self._build.detected(
                "violation-count",
                category="automated-testing",
                name="Accessibility violations",
                value=total_violations,
                unit="count",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.AXE_RESULT,
                        source="accessibility.violations",
                        excerpt=(
                            f"{total_violations} rules violated, {total_nodes} total nodes affected"
                        ),
                    )
                ],
                details={
                    "total_nodes_affected": total_nodes,
                    "rules_run": axe.rules_run_count,
                    "passes": axe.passes_count,
                },
                limitations=limitations,
            )
        )

        # By impact level
        impact_counts: dict[str, int] = {}
        for v in axe.violations:
            impact = v.impact or "unknown"
            impact_counts[impact] = impact_counts.get(impact, 0) + 1

        if impact_counts:
            findings.append(
                self._build.detected(
                    "violations-by-impact",
                    category="automated-testing",
                    name="Violations by impact",
                    value=len(impact_counts),
                    unit="count",
                    values=[
                        f"{impact}: {count}"
                        for impact, count in sorted(
                            impact_counts.items(),
                            key=lambda x: (
                                ["critical", "serious", "moderate", "minor"].index(x[0])
                                if x[0] in ["critical", "serious", "moderate", "minor"]
                                else 99
                            ),
                        )
                    ],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.AXE_RESULT,
                            source="accessibility.violations[impact]",
                            excerpt=", ".join(f"{k}={v}" for k, v in impact_counts.items()),
                        )
                    ],
                    limitations=limitations,
                )
            )

        # Top violations
        for v in axe.violations[:10]:
            slug = f"rule-{v.rule_id}"
            findings.append(
                self._build.detected(
                    slug,
                    category="automated-testing",
                    name=f"Violation: {v.rule_id}",
                    value=v.node_count,
                    unit="count",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.AXE_RESULT,
                            source=f"accessibility.violations[{v.rule_id}]",
                            excerpt=v.help_text[:200] if v.help_text else v.description[:200],
                        )
                    ],
                    details={
                        "impact": v.impact,
                        "help_url": v.help_url,
                    },
                    limitations=limitations,
                )
            )

        return AnalyzerOutput(
            findings=findings,
            data=DesignPayload(axe=axe),
            limitations=limitations,
        )
