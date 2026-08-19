"""Security response header analysis.

Checks for the presence and quality of security-relevant HTTP response headers:
HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
Permissions-Policy, and Cross-Origin policies.
"""

from __future__ import annotations

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
    header_evidence,
)
from weblens.domain.enums import Confidence, EvidenceSlot, SectionKey
from weblens.domain.sections import HeaderObservationSummary, SecurityPayload

ANALYZER_ID = "security.headers"

CATEGORY = "response_headers"


class SecurityHeadersAnalyzer:
    """Checks security response headers."""

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
        header_summaries: list[HeaderObservationSummary] = []

        # HTTPS check
        final_url = http.final_url
        is_https = final_url.startswith("https://")
        if is_https:
            findings.append(
                self._build.detected(
                    "https",
                    category=CATEGORY,
                    name="HTTPS",
                    value=True,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("url", final_url)],
                )
            )
        else:
            findings.append(
                self._build.detected(
                    "https",
                    category=CATEGORY,
                    name="HTTPS",
                    value=False,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("url", final_url)],
                )
            )

        # HSTS
        hsts = http.header("strict-transport-security")
        header_summaries.append(
            HeaderObservationSummary(
                name="strict-transport-security", present=hsts is not None, value=hsts
            )
        )
        if hsts:
            findings.append(
                self._build.detected(
                    "hsts",
                    category=CATEGORY,
                    name="Strict-Transport-Security (HSTS)",
                    value=hsts,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("strict-transport-security", hsts)],
                    details={"include_subdomains": "includesubdomains" in hsts.lower()},
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "hsts",
                    category=CATEGORY,
                    name="Strict-Transport-Security (HSTS)",
                    reason="No Strict-Transport-Security header was present in the response.",
                )
            )

        # CSP
        csp = http.header("content-security-policy")
        header_summaries.append(
            HeaderObservationSummary(
                name="content-security-policy", present=csp is not None, value=csp
            )
        )
        if csp:
            findings.append(
                self._build.detected(
                    "csp",
                    category=CATEGORY,
                    name="Content-Security-Policy",
                    value=csp[:200],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("content-security-policy", csp)],
                    details={
                        "has_default_src": "default-src" in csp,
                        "has_script_src": "script-src" in csp,
                        "has_unsafe_inline": "'unsafe-inline'" in csp,
                        "has_unsafe_eval": "'unsafe-eval'" in csp,
                    },
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "csp",
                    category=CATEGORY,
                    name="Content-Security-Policy",
                    reason="No Content-Security-Policy header was present.",
                )
            )

        # X-Content-Type-Options
        xcto = http.header("x-content-type-options")
        header_summaries.append(
            HeaderObservationSummary(
                name="x-content-type-options", present=xcto is not None, value=xcto
            )
        )
        if xcto:
            findings.append(
                self._build.detected(
                    "x-content-type-options",
                    category=CATEGORY,
                    name="X-Content-Type-Options",
                    value=xcto,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("x-content-type-options", xcto)],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "x-content-type-options",
                    category=CATEGORY,
                    name="X-Content-Type-Options",
                    reason="No X-Content-Type-Options header was present.",
                )
            )

        # X-Frame-Options
        xfo = http.header("x-frame-options")
        header_summaries.append(
            HeaderObservationSummary(name="x-frame-options", present=xfo is not None, value=xfo)
        )
        if xfo:
            findings.append(
                self._build.detected(
                    "x-frame-options",
                    category=CATEGORY,
                    name="X-Frame-Options",
                    value=xfo,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("x-frame-options", xfo)],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "x-frame-options",
                    category=CATEGORY,
                    name="X-Frame-Options",
                    reason="No X-Frame-Options header was present.",
                )
            )

        # Referrer-Policy
        rp = http.header("referrer-policy")
        header_summaries.append(
            HeaderObservationSummary(name="referrer-policy", present=rp is not None, value=rp)
        )
        if rp:
            findings.append(
                self._build.detected(
                    "referrer-policy",
                    category=CATEGORY,
                    name="Referrer-Policy",
                    value=rp,
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("referrer-policy", rp)],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "referrer-policy",
                    category=CATEGORY,
                    name="Referrer-Policy",
                    reason="No Referrer-Policy header was present.",
                )
            )

        # Permissions-Policy
        pp = http.header("permissions-policy")
        header_summaries.append(
            HeaderObservationSummary(name="permissions-policy", present=pp is not None, value=pp)
        )
        if pp:
            findings.append(
                self._build.detected(
                    "permissions-policy",
                    category=CATEGORY,
                    name="Permissions-Policy",
                    value=pp[:200],
                    confidence=Confidence.DEFINITIVE,
                    evidence=[header_evidence("permissions-policy", pp)],
                )
            )
        else:
            findings.append(
                self._build.not_detected(
                    "permissions-policy",
                    category=CATEGORY,
                    name="Permissions-Policy",
                    reason="No Permissions-Policy header was present.",
                )
            )

        # HTTP -> HTTPS redirect
        if http.http_origin_redirects_to_https is not None:
            if http.http_origin_redirects_to_https:
                findings.append(
                    self._build.detected(
                        "http-redirect",
                        category=CATEGORY,
                        name="HTTP to HTTPS redirect",
                        value=True,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            header_evidence(
                                "http-origin-probe",
                                f"Redirects to HTTPS (status {http.http_origin_redirect_status})",
                            )
                        ],
                    )
                )
            else:
                findings.append(
                    self._build.detected(
                        "http-redirect",
                        category=CATEGORY,
                        name="HTTP to HTTPS redirect",
                        value=False,
                        confidence=Confidence.DEFINITIVE,
                        evidence=[
                            header_evidence(
                                "http-origin-probe",
                                "Does not redirect to HTTPS "
                                f"(status {http.http_origin_redirect_status})",
                            )
                        ],
                    )
                )

        return AnalyzerOutput(
            findings=findings,
            data=SecurityPayload(headers=header_summaries),
        )
