"""Third-party domain and first/third-party split analysis."""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.utils.urls import registrable_suffix_match

ANALYZER_ID = "network.third_parties"


class NetworkThirdPartiesAnalyzer:
    """Analyzes first-party vs third-party request distribution."""

    id = ANALYZER_ID
    section = SectionKey.NETWORK
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.NETWORK})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        network = ctx.evidence.network
        if network is None:
            return AnalyzerOutput(findings=[])

        target_host = ctx.evidence.target.host
        findings = []

        first_party = 0
        third_party = 0
        tp_domains: set[str] = set()

        for req in network.requests:
            host = req.host or "unknown"
            if registrable_suffix_match(host, target_host):
                first_party += 1
            else:
                third_party += 1
                tp_domains.add(host)

        total = first_party + third_party
        if total > 0:
            tp_pct = round((third_party / total) * 100, 1)
            findings.append(
                self._build.detected(
                    "third-party-ratio",
                    category="network",
                    name="Third-party request ratio",
                    value=tp_pct,
                    unit="%",
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.NETWORK_REQUEST,
                            source="network.requests",
                            excerpt=f"{third_party}/{total} requests ({tp_pct}%) to third parties",
                        )
                    ],
                    details={
                        "first_party": first_party,
                        "third_party": third_party,
                        "third_party_domains": len(tp_domains),
                    },
                )
            )

            if tp_domains:
                findings.append(
                    self._build.detected(
                        "third-party-domains",
                        category="network",
                        name="Third-party domains",
                        value=len(tp_domains),
                        unit="count",
                        values=sorted(tp_domains)[:20],
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.NETWORK_REQUEST,
                                source="network.requests[third_party]",
                                excerpt=", ".join(sorted(tp_domains)[:5]),
                            )
                        ],
                    )
                )

        return AnalyzerOutput(findings=findings)
