"""Mixed content and insecure resource detection.

Detects: HTTP resources loaded on HTTPS pages, insecure form actions.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef
from weblens.utils.urls import is_insecure_http

ANALYZER_ID = "security.mixed_content"


class SecurityMixedContentAnalyzer:
    """Detects mixed content (HTTP resources on HTTPS pages)."""

    id = ANALYZER_ID
    section = SectionKey.SECURITY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.DOM, EvidenceSlot.NETWORK})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        dom = ctx.evidence.dom
        network = ctx.evidence.network
        http = ctx.evidence.http

        if dom is None and network is None:
            return AnalyzerOutput(findings=[])

        # Only relevant for HTTPS pages
        final_url = http.final_url if http else ""
        if not final_url.startswith("https://"):
            return AnalyzerOutput(
                findings=[
                    self._build.not_detected(
                        "mixed-content",
                        category="content_integrity",
                        name="Mixed content",
                        reason="The page is served over HTTP, so mixed content does not apply.",
                    )
                ]
            )

        findings = []
        insecure_resources: list[str] = []

        # Check network requests for HTTP resources
        if network:
            for req in network.requests:
                if is_insecure_http(req.url) and not req.failed:
                    insecure_resources.append(req.url)

        # Check DOM for insecure references
        if dom:
            for script in dom.scripts:
                if script.src and is_insecure_http(script.src):
                    insecure_resources.append(script.src)
            for img in dom.images:
                if img.src and is_insecure_http(img.src):
                    insecure_resources.append(img.src)
            for form in dom.forms:
                if form.action and is_insecure_http(form.action):
                    insecure_resources.append(f"form action: {form.action}")

        insecure_resources = list(dict.fromkeys(insecure_resources))[:20]

        if insecure_resources:
            findings.append(
                self._build.detected(
                    "mixed-content",
                    category="content_integrity",
                    name="Mixed content (insecure resources)",
                    value=len(insecure_resources),
                    unit="count",
                    values=insecure_resources[:10],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.NETWORK_REQUEST,
                            source="network.requests[scheme=http]",
                            excerpt=insecure_resources[0][:200],
                        )
                    ],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "mixed-content",
                    category="content_integrity",
                    name="Mixed content",
                    reason="No HTTP resources were loaded on this HTTPS page.",
                )
            )

        return AnalyzerOutput(findings=findings)
