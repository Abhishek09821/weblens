"""Cookie security attribute analysis.

Observes: Secure flag, HttpOnly flag, SameSite attribute on observed cookies.
Cookie values are never captured or stored.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import Confidence, EvidenceKind, EvidenceSlot, SectionKey
from weblens.domain.evidence import EvidenceRef

ANALYZER_ID = "security.cookies"


class SecurityCookiesAnalyzer:
    """Analyzes cookie security attributes."""

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

        cookies = http.cookies
        if not cookies:
            findings = [
                self._build.not_detected(
                    "cookies-observed",
                    category="cookies",
                    name="Cookies",
                    reason="No Set-Cookie headers were observed in the response.",
                )
            ]
            return AnalyzerOutput(findings=findings)

        findings = []
        total = len(cookies)

        # Total cookies
        findings.append(
            self._build.detected(
                "cookies-observed",
                category="cookies",
                name="Cookies observed",
                value=total,
                unit="count",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.COOKIE,
                        source="http.cookies",
                        excerpt=f"{total} cookies set",
                    )
                ],
            )
        )

        # Secure flag
        insecure = [c.name for c in cookies if not c.secure]
        if insecure:
            findings.append(
                self._build.detected(
                    "missing-secure",
                    category="cookies",
                    name="Cookies without Secure flag",
                    value=len(insecure),
                    unit="count",
                    values=insecure[:10],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.COOKIE,
                            source="http.cookies[secure=false]",
                            excerpt=f"Cookies without Secure: {', '.join(insecure[:5])}",
                        )
                    ],
                )
            )

        # HttpOnly flag
        no_httponly = [c.name for c in cookies if not c.http_only]
        if no_httponly:
            findings.append(
                self._build.detected(
                    "missing-httponly",
                    category="cookies",
                    name="Cookies without HttpOnly flag",
                    value=len(no_httponly),
                    unit="count",
                    values=no_httponly[:10],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.COOKIE,
                            source="http.cookies[http_only=false]",
                            excerpt=f"Cookies without HttpOnly: {', '.join(no_httponly[:5])}",
                        )
                    ],
                )
            )

        # SameSite
        no_samesite = [c.name for c in cookies if not c.same_site]
        if no_samesite:
            findings.append(
                self._build.detected(
                    "missing-samesite",
                    category="cookies",
                    name="Cookies without SameSite attribute",
                    value=len(no_samesite),
                    unit="count",
                    values=no_samesite[:10],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[
                        EvidenceRef(
                            kind=EvidenceKind.COOKIE,
                            source="http.cookies[same_site=null]",
                            excerpt=f"Cookies without SameSite: {', '.join(no_samesite[:5])}",
                        )
                    ],
                )
            )

        return AnalyzerOutput(findings=findings)
