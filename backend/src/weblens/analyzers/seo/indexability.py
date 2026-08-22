"""SEO indexability analysis.

Checks: robots.txt directives, X-Robots-Tag, canonical self-reference,
redirect chain shape, sitemaps.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    header_evidence,
    robots_evidence,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import IndexabilityObservation, TechnologyPayload

ANALYZER_ID = "seo.indexability"


class SeoIndexabilityAnalyzer:
    """Checks indexability signals."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.HTTP, EvidenceSlot.ROBOTS})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        http = ctx.evidence.http
        robots_obs = ctx.evidence.robots

        if http is None and robots_obs is None:
            return AnalyzerOutput(findings=[])

        findings = []
        robots_allowed: bool | None = None
        x_robots: str | None = None
        canonical_self: bool | None = None
        sitemaps: list[str] = []
        redirect_hops: int | None = None

        # Robots.txt
        if robots_obs:
            robots_allowed = robots_obs.allowed
            sitemaps = robots_obs.sitemaps[:10]

            if robots_obs.allowed is True:
                findings.append(
                    self._build.detected(
                        "robots-allowed",
                        category="indexability",
                        name="robots.txt allows access",
                        value=True,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.ROBOTS_DIRECTIVE,
                                source="robots.allowed",
                                excerpt=robots_obs.matched_directive or "No restriction found",
                                location=robots_obs.url,
                            )
                        ],
                    )
                )
            elif robots_obs.allowed is False:
                findings.append(
                    self._build.detected(
                        "robots-disallowed",
                        category="indexability",
                        name="robots.txt disallows access",
                        value=True,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            robots_evidence(
                                robots_obs.matched_directive or "Disallow", robots_obs.url
                            )
                        ],
                    )
                )

            if sitemaps:
                findings.append(
                    self._build.detected(
                        "sitemaps",
                        category="indexability",
                        name="Sitemaps declared in robots.txt",
                        value=len(sitemaps),
                        unit="count",
                        values=sitemaps[:10],
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.ROBOTS_DIRECTIVE,
                                source="robots.sitemaps",
                                excerpt=sitemaps[0],
                                location=robots_obs.url,
                            )
                        ],
                    )
                )

        # X-Robots-Tag
        if http:
            x_robots = http.header("x-robots-tag")
            if x_robots:
                findings.append(
                    self._build.detected(
                        "x-robots-tag",
                        category="indexability",
                        name="X-Robots-Tag header",
                        value=x_robots,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[header_evidence("x-robots-tag", x_robots)],
                    )
                )

            # Redirect hop count
            redirect_hops = len(http.hops) - 1 if http.hops else 0
            if redirect_hops > 0:
                findings.append(
                    self._build.detected(
                        "redirect-hops",
                        category="indexability",
                        name="Redirect hop count",
                        value=redirect_hops,
                        unit="count",
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            EvidenceRef(
                                kind=EvidenceKind.REDIRECT_HOP,
                                source="http.hops",
                                excerpt=f"{redirect_hops} redirects before final URL",
                            )
                        ],
                    )
                )

        # Canonical self-reference check
        dom = ctx.evidence.dom
        if dom and http:
            canonical_link = None
            for link in dom.link_tags:
                if link.rel and "canonical" in link.rel.lower():
                    canonical_link = link.href
                    break
            if canonical_link:
                canonical_self = canonical_link.rstrip("/") == http.final_url.rstrip("/")
                if canonical_self:
                    findings.append(
                        self._build.detected(
                            "canonical-self",
                            category="indexability",
                            name="Canonical is self-referential",
                            value=True,
                            confidence=Confidence.DEFINITIVE,
                            evidence=[
                                EvidenceRef(
                                    kind=EvidenceKind.HTML_ELEMENT,
                                    source="dom.link[rel=canonical]",
                                    excerpt=canonical_link,
                                )
                            ],
                        )
                    )

        indexability_obs = IndexabilityObservation(
            robots_txt_allowed=robots_allowed,
            x_robots_tag=x_robots,
            canonical_is_self_referential=canonical_self,
            redirect_hop_count=redirect_hops,
            sitemaps=sitemaps,
        )

        return AnalyzerOutput(
            findings=findings,
            data=TechnologyPayload(indexability=indexability_obs),
        )
