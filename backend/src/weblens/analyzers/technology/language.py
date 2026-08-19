"""Server-side language/runtime detection from response headers.

Only reports what headers actually disclose. Never guesses from URL patterns alone.
"""

from __future__ import annotations

import re

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    header_evidence,
)
from weblens.domain.enums import Confidence, EvidenceSlot, SectionKey
from weblens.domain.sections import DetectedProduct, TechnologyPayload

ANALYZER_ID = "technology.language"

# Header patterns that reliably indicate server-side technology
_PATTERNS: list[tuple[str, str, re.Pattern[str], list[str]]] = [
    (
        "x-powered-by",
        "PHP",
        re.compile(r"PHP[/ ]?([\d.]+)?", re.IGNORECASE),
        ["language", "runtime"],
    ),
    ("x-powered-by", "ASP.NET", re.compile(r"ASP\.NET", re.IGNORECASE), ["framework", "runtime"]),
    ("x-powered-by", "Express", re.compile(r"Express", re.IGNORECASE), ["framework", "runtime"]),
    ("x-aspnet-version", "ASP.NET", re.compile(r".+"), ["framework", "runtime"]),
    ("x-powered-by", "Next.js", re.compile(r"Next\.js", re.IGNORECASE), ["meta-framework"]),
    ("x-powered-by", "Nuxt", re.compile(r"Nuxt", re.IGNORECASE), ["meta-framework"]),
    ("server", "Apache", re.compile(r"Apache[/ ]?([\d.]+)?", re.IGNORECASE), ["web-server"]),
    ("server", "nginx", re.compile(r"nginx[/ ]?([\d.]+)?", re.IGNORECASE), ["web-server"]),
    ("server", "LiteSpeed", re.compile(r"LiteSpeed", re.IGNORECASE), ["web-server"]),
    (
        "server",
        "Microsoft-IIS",
        re.compile(r"Microsoft-IIS[/ ]?([\d.]+)?", re.IGNORECASE),
        ["web-server"],
    ),
    ("server", "Caddy", re.compile(r"Caddy", re.IGNORECASE), ["web-server"]),
    (
        "x-powered-by",
        "Phusion Passenger",
        re.compile(r"Phusion Passenger", re.IGNORECASE),
        ["app-server"],
    ),
    ("x-generator", "Drupal", re.compile(r"Drupal", re.IGNORECASE), ["cms"]),
    ("x-generator", "WordPress", re.compile(r"WordPress", re.IGNORECASE), ["cms"]),
]


class TechLanguageAnalyzer:
    """Detects server-side language/runtime from response headers."""

    id = ANALYZER_ID
    section = SectionKey.TECHNOLOGY
    version = "1.0.0"
    requires = frozenset({EvidenceSlot.HTTP})
    depends_on: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        http = ctx.evidence.http
        if http is None:
            return AnalyzerOutput(findings=[])

        findings = []
        products: list[DetectedProduct] = []
        seen_names: set[str] = set()

        for header_name, tech_name, pattern, categories in _PATTERNS:
            if tech_name in seen_names:
                continue
            header_val = http.header(header_name)
            if header_val is None:
                continue
            match = pattern.search(header_val)
            if not match:
                continue

            seen_names.add(tech_name)
            version = match.group(1) if match.groups() and match.group(1) else None
            slug = tech_name.lower().replace(" ", "-").replace(".", "-")

            finding = self._build.detected(
                slug,
                category="server-technology",
                name=tech_name,
                value=f"{tech_name}/{version}" if version else tech_name,
                confidence=Confidence.DEFINITIVE,
                evidence=[header_evidence(header_name, header_val)],
            )
            findings.append(finding)
            products.append(
                DetectedProduct(
                    name=tech_name,
                    categories=categories,
                    version=version,
                    status=finding.status,
                    signal_summary=[f"Header '{header_name}': {header_val[:80]}"],
                    finding_id=finding.id,
                )
            )

        if not findings:
            findings.append(
                self._build.not_detected(
                    "server-technology",
                    category="server-technology",
                    name="Server-side technology",
                    reason="No recognizable server technology was disclosed in response headers.",
                )
            )

        return AnalyzerOutput(
            findings=findings,
            data=TechnologyPayload(products=products) if products else None,
        )
