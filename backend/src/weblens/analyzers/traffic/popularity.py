"""Traffic popularity analyzer.

Produces findings about domain popularity/traffic based on external public data sources.
When no traffic provider is configured, all findings are reported as UNABLE_TO_VERIFY
with an honest explanation of why.

This analyzer never fabricates exact visit counts.
"""

from __future__ import annotations

from weblens.analyzers.base import AnalyzerContext, AnalyzerOutput, FindingBuilder
from weblens.domain.enums import EvidenceSlot, SectionKey

ANALYZER_ID = "traffic.popularity"


class TrafficPopularityAnalyzer:
    """Stub traffic popularity analyzer.

    In the current build this reports that no traffic provider is configured.
    When a TrafficProvider implementation is wired in, this analyzer will
    consume its output to produce ranked popularity findings.
    """

    id = ANALYZER_ID
    section = SectionKey.TRAFFIC
    version = "1.0.0"
    requires = frozenset[EvidenceSlot]()
    depends_on = frozenset[str]()

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        fb = FindingBuilder(self.id)
        findings = []

        # Without a traffic provider, report honestly.
        findings.append(
            fb.unable_to_verify(
                "domain-rank",
                category="popularity",
                name="Domain popularity rank",
                reason="No traffic data provider is configured in this build. "
                "Public ranking data requires an external data source.",
                limitations=[
                    "Traffic estimation requires a configured provider (e.g. Tranco, CrUX).",
                    "No exact visit counts can be determined from passive observation alone.",
                ],
            )
        )

        findings.append(
            fb.unable_to_verify(
                "traffic-band",
                category="popularity",
                name="Traffic band estimate",
                reason="No traffic data provider is configured in this build.",
                limitations=[
                    "Traffic bands require a credible public data source.",
                ],
            )
        )

        return AnalyzerOutput(
            findings=findings,
            limitations=[
                "Traffic intelligence requires an external data provider. "
                "Without one, this section cannot produce findings.",
            ],
        )
