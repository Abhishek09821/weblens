"""Network resource ledger: per-domain counts and bytes, protocol mix."""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import DomainSummary, NetworkPayload
from weblens.utils.urls import registrable_suffix_match

ANALYZER_ID = "network.resources"


class NetworkResourcesAnalyzer:
    """Produces the network request summary and domain breakdown."""

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

        findings = []
        target_host = ctx.evidence.target.host

        # Per-domain breakdown
        domain_data: dict[str, dict[str, int]] = {}
        for req in network.requests:
            host = req.host or "unknown"
            if host not in domain_data:
                domain_data[host] = {"count": 0, "bytes": 0}
            domain_data[host]["count"] += 1
            if req.transfer_bytes:
                domain_data[host]["bytes"] += req.transfer_bytes

        by_domain = []
        for host, data in sorted(domain_data.items(), key=lambda x: x[1]["count"], reverse=True):
            is_third_party = not registrable_suffix_match(host, target_host)
            by_domain.append(
                DomainSummary(
                    host=host,
                    request_count=data["count"],
                    transfer_bytes=data["bytes"] if data["bytes"] > 0 else None,
                    is_third_party=is_third_party,
                )
            )

        # Findings
        findings.append(
            self._build.detected(
                "domain-count",
                category="network",
                name="Unique domains",
                value=len(domain_data),
                unit="count",
                values=[f"{d.host}: {d.request_count} requests" for d in by_domain[:10]],
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.NETWORK_REQUEST,
                        source="network.requests.host",
                        excerpt=f"{len(domain_data)} unique domains",
                    )
                ],
            )
        )

        return AnalyzerOutput(
            findings=findings,
            data=NetworkPayload(
                requests=network.requests,
                by_domain=by_domain[:50],
                cap_hit=network.cap_hit,
            ),
        )
