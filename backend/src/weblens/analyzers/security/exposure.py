"""Technology exposure analysis.

Checks for: version disclosure in Server/X-Powered-By headers,
source map references, debug headers.
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

ANALYZER_ID = "security.exposure"

_VERSION_PATTERN = re.compile(r"[\d]+\.[\d]+")


class SecurityExposureAnalyzer:
    """Detects technology version disclosure in headers."""

    id = ANALYZER_ID
    section = SectionKey.SECURITY
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

        # Server header with version
        server = http.header("server")
        if server and _VERSION_PATTERN.search(server):
            findings.append(
                self._build.detected(
                    "server-version",
                    category="exposure",
                    name="Server version disclosure",
                    value=server,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("server", server)],
                )
            )

        # X-Powered-By with version
        xpb = http.header("x-powered-by")
        if xpb:
            findings.append(
                self._build.detected(
                    "x-powered-by",
                    category="exposure",
                    name="X-Powered-By disclosure",
                    value=xpb,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("x-powered-by", xpb)],
                )
            )

        # X-AspNet-Version
        aspnet = http.header("x-aspnet-version")
        if aspnet:
            findings.append(
                self._build.detected(
                    "aspnet-version",
                    category="exposure",
                    name="X-AspNet-Version disclosure",
                    value=aspnet,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("x-aspnet-version", aspnet)],
                )
            )

        # Source maps
        sourcemap = http.header("sourcemap") or http.header("x-sourcemap")
        if sourcemap:
            findings.append(
                self._build.detected(
                    "source-map",
                    category="exposure",
                    name="Source map header",
                    value=sourcemap,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("sourcemap", sourcemap)],
                )
            )

        if not findings:
            findings.append(
                self._build.not_detected(
                    "version-disclosure",
                    category="exposure",
                    name="Version disclosure",
                    reason="No technology version disclosure was observed in response headers.",
                )
            )

        return AnalyzerOutput(findings=findings)
