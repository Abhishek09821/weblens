"""Hosting and CDN platform detection from headers.

Reports hosting platform and CDN indicators from response headers and DNS.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    header_evidence,
)
from weblens.domain.enums import Confidence, EvidenceSlot, SectionKey

ANALYZER_ID = "architecture.platform"

# Platform detection from headers
_PLATFORM_HEADERS: list[tuple[str, str, str]] = [
    ("x-vercel-id", "Vercel", "hosting"),
    ("x-nf-request-id", "Netlify", "hosting"),
    ("x-amz-cf-id", "AWS CloudFront", "cdn"),
    ("x-github-request-id", "GitHub Pages", "hosting"),
    ("x-powered-by-plesk", "Plesk", "hosting"),
    ("x-fw-hash", "Flywheel", "hosting"),
    ("x-kinsta-cache", "Kinsta", "hosting"),
    ("cf-ray", "Cloudflare", "cdn"),
    ("x-cache", "CDN Cache", "cdn"),
]


class ArchitecturePlatformAnalyzer:
    """Detects hosting and CDN platform from headers."""

    id = ANALYZER_ID
    section = SectionKey.ARCHITECTURE
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.HTTP, EvidenceSlot.DNS})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        http = ctx.evidence.http
        if http is None:
            return AnalyzerOutput(findings=[])

        findings = []

        for header_name, platform_name, category in _PLATFORM_HEADERS:
            value = http.header(header_name)
            if value:
                slug = platform_name.lower().replace(" ", "-")
                findings.append(
                    self._build.detected(
                        slug,
                        category="platform",
                        name=f"Platform: {platform_name}",
                        value=platform_name,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[header_evidence(header_name, value)],
                        details={"type": category},
                    )
                )

        # HTTP protocol version
        if http.http_version:
            findings.append(
                self._build.detected(
                    "http-protocol",
                    category="protocol",
                    name="HTTP protocol version",
                    value=http.http_version,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("protocol", http.http_version)],
                )
            )

        if not findings:
            findings.append(
                self._build.not_detected(
                    "platform",
                    category="platform",
                    name="Hosting platform",
                    reason="No identifiable platform headers were observed.",
                )
            )

        return AnalyzerOutput(findings=findings)
