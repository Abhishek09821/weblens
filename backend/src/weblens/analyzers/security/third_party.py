"""Third-party script surface and SRI coverage analysis."""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.utils.urls import host_of, registrable_suffix_match

ANALYZER_ID = "security.third_party"


class SecurityThirdPartyAnalyzer:
    """Analyzes cross-origin scripts and SRI usage."""

    id = ANALYZER_ID
    section = SectionKey.SECURITY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM, EvidenceSlot.NETWORK})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        if dom is None:
            return AnalyzerOutput(findings=[])

        target_host = ctx.evidence.target.host
        findings = []

        # Cross-origin scripts
        cross_origin_scripts: list[str] = []
        scripts_with_sri = 0
        scripts_without_sri = 0

        for script in dom.scripts:
            if not script.src:
                continue
            script_host = host_of(script.src)
            if script_host and not registrable_suffix_match(script_host, target_host):
                cross_origin_scripts.append(script.src)
                if script.integrity:
                    scripts_with_sri += 1
                else:
                    scripts_without_sri += 1

        if cross_origin_scripts:
            findings.append(
                self._build.detected(
                    "cross-origin-scripts",
                    category="content_integrity",
                    name="Cross-origin scripts",
                    value=len(cross_origin_scripts),
                    unit="count",
                    values=cross_origin_scripts[:10],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.SCRIPT_URL,
                            source="dom.scripts[cross-origin]",
                            excerpt=cross_origin_scripts[0][:200],
                        )
                    ],
                )
            )

            # SRI coverage
            total_co = len(cross_origin_scripts)
            if scripts_without_sri > 0:
                findings.append(
                    self._build.detected(
                        "sri-missing",
                        category="content_integrity",
                        name="Cross-origin scripts without SRI",
                        value=scripts_without_sri,
                        unit="count",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.SCRIPT_URL,
                                source="dom.scripts[cross-origin, no integrity]",
                                excerpt=(
                                    f"{scripts_without_sri}/{total_co} "
                                    "without integrity attribute"
                                ),
                            )
                        ],
                        details={"with_sri": scripts_with_sri, "without_sri": scripts_without_sri},
                    )
                )
        else:
            findings.append(
                self._build.not_detected(
                    "cross-origin-scripts",
                    category="content_integrity",
                    name="Cross-origin scripts",
                    reason="No cross-origin script elements were observed.",
                )
            )

        return AnalyzerOutput(findings=findings)
