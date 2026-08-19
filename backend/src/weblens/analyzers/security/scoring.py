"""Security posture scoring.

Applies a transparent rule table to the security findings produced by other
security analyzers. The methodology is fully documented in the score output.

NEVER claims a site is "secure" or "insecure". Only reports the observable
posture of externally visible security controls.
"""

from __future__ import annotations

from dataclasses import dataclass

from weblens.analyzers.base import (
    AnalyzerContext,
    AnalyzerOutput,
    FindingBuilder,
)
from weblens.domain.enums import (
    Confidence,
    EvidenceKind,
    EvidenceSlot,
    PostureBand,
    RuleOutcome,
    SectionKey,
    SecurityCategory,
)
from weblens.domain.evidence import EvidenceRef
from weblens.domain.sections import SecurityPayload
from weblens.domain.security import (
    BAND_PHRASING,
    AppliedCap,
    ExcludedRule,
    SecurityRuleResult,
    SecurityScore,
)

ANALYZER_ID = "security.scoring"
METHODOLOGY_VERSION = "1.0.0"


@dataclass(frozen=True)
class _ScoringRule:
    id: str
    title: str
    category: SecurityCategory
    weight: float
    finding_id: str  # The finding this rule checks
    pass_when_detected: bool = True  # Pass when the finding is detected (present)
    pass_value: object = None  # If set, the finding value must equal this
    partial_condition: str | None = None  # Partial pass condition description


# Scoring rules - deterministic, transparent
RULES: list[_ScoringRule] = [
    _ScoringRule(
        "TLS-01",
        "HTTPS",
        SecurityCategory.TRANSPORT,
        15.0,
        "security.headers:https",
        pass_value=True,
    ),
    _ScoringRule(
        "TLS-02",
        "HTTP to HTTPS redirect",
        SecurityCategory.TRANSPORT,
        5.0,
        "security.headers:http-redirect",
        pass_value=True,
    ),
    _ScoringRule("HDR-01", "HSTS header", SecurityCategory.HEADERS, 10.0, "security.headers:hsts"),
    _ScoringRule(
        "HDR-02", "Content-Security-Policy", SecurityCategory.HEADERS, 15.0, "security.headers:csp"
    ),
    _ScoringRule(
        "HDR-03",
        "X-Content-Type-Options",
        SecurityCategory.HEADERS,
        5.0,
        "security.headers:x-content-type-options",
    ),
    _ScoringRule(
        "HDR-04",
        "X-Frame-Options",
        SecurityCategory.HEADERS,
        5.0,
        "security.headers:x-frame-options",
    ),
    _ScoringRule(
        "HDR-05",
        "Referrer-Policy",
        SecurityCategory.HEADERS,
        5.0,
        "security.headers:referrer-policy",
    ),
    _ScoringRule(
        "HDR-06",
        "Permissions-Policy",
        SecurityCategory.HEADERS,
        5.0,
        "security.headers:permissions-policy",
    ),
    _ScoringRule(
        "COK-01",
        "No cookies without Secure",
        SecurityCategory.COOKIES,
        10.0,
        "security.cookies:missing-secure",
        pass_when_detected=False,
    ),
    _ScoringRule(
        "COK-02",
        "No cookies without HttpOnly",
        SecurityCategory.COOKIES,
        5.0,
        "security.cookies:missing-httponly",
        pass_when_detected=False,
    ),
    _ScoringRule(
        "COK-03",
        "No cookies without SameSite",
        SecurityCategory.COOKIES,
        5.0,
        "security.cookies:missing-samesite",
        pass_when_detected=False,
    ),
    _ScoringRule(
        "MIX-01",
        "No mixed content",
        SecurityCategory.CONTENT_INTEGRITY,
        10.0,
        "security.mixed_content:mixed-content",
        pass_when_detected=False,
    ),
    _ScoringRule(
        "EXP-01",
        "No server version disclosure",
        SecurityCategory.EXPOSURE,
        5.0,
        "security.exposure:server-version",
        pass_when_detected=False,
    ),
]


def _band_for(percentage: float) -> PostureBand:
    if percentage >= 90:
        return PostureBand.STRONG
    if percentage >= 70:
        return PostureBand.GOOD
    if percentage >= 50:
        return PostureBand.MODERATE
    if percentage >= 30:
        return PostureBand.LIMITED
    return PostureBand.MINIMAL


class SecurityScoringAnalyzer:
    """Computes the security posture score from other security findings."""

    id = ANALYZER_ID
    section = SectionKey.SECURITY
    version = "1.0.0"
    requires: frozenset[EvidenceSlot] = frozenset()
    depends_on = frozenset(
        {
            "security.headers",
            "security.cookies",
            "security.tls",
            "security.mixed_content",
            "security.third_party",
            "security.exposure",
        }
    )

    def __init__(self) -> None:
        self._build = FindingBuilder(ANALYZER_ID)

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        produced = ctx.findings
        rule_results: list[SecurityRuleResult] = []
        excluded: list[ExcludedRule] = []
        caps: list[AppliedCap] = []

        total_applicable = 0.0
        total_awarded = 0.0

        for rule in RULES:
            finding = produced.get(rule.finding_id)

            if finding is None:
                # Finding not produced - exclude from score
                excluded.append(
                    ExcludedRule(
                        id=rule.id,
                        outcome=RuleOutcome.UNKNOWN,
                        reason=f"Required finding '{rule.finding_id}' was not produced.",
                    )
                )
                continue

            # Determine outcome
            if rule.pass_value is not None:
                # Check specific value
                if finding.value == rule.pass_value:
                    outcome = RuleOutcome.PASS
                    awarded = rule.weight
                else:
                    outcome = RuleOutcome.FAIL
                    awarded = 0.0
            elif rule.pass_when_detected:
                # Pass when the finding is detected (header present)
                if finding.detected:
                    outcome = RuleOutcome.PASS
                    awarded = rule.weight
                else:
                    outcome = RuleOutcome.FAIL
                    awarded = 0.0
            else:
                # Pass when the finding is NOT detected (no bad thing found)
                if not finding.detected:
                    outcome = RuleOutcome.PASS
                    awarded = rule.weight
                else:
                    outcome = RuleOutcome.FAIL
                    awarded = 0.0

            total_applicable += rule.weight
            total_awarded += awarded

            rationale = (
                f"{'Present' if finding.detected else 'Not present'}: "
                f"{finding.value if finding.value else finding.reason or 'N/A'}"
            )[:200]

            rule_results.append(
                SecurityRuleResult(
                    id=rule.id,
                    title=rule.title,
                    category=rule.category,
                    outcome=outcome,
                    weight=rule.weight,
                    awarded=awarded,
                    rationale=rationale,
                    evidence=finding.evidence[:3],
                )
            )

        # Calculate percentage
        percentage = (
            round((total_awarded / total_applicable) * 100, 1) if total_applicable > 0 else 0.0
        )
        band = _band_for(percentage)

        score = SecurityScore(
            methodology_version=METHODOLOGY_VERSION,
            points_awarded=total_awarded,
            points_applicable=total_applicable,
            percentage=percentage,
            band=band,
            band_phrase=BAND_PHRASING[band],
            rules=rule_results,
            excluded_rules=excluded,
            applied_caps=caps,
        )

        # Produce a summary finding
        findings = [
            self._build.detected(
                "posture-score",
                category="overall",
                name="Observable Security Posture",
                value=percentage,
                unit="%",
                confidence=Confidence.DEFINITIVE,
                evidence=[
                    EvidenceRef(
                        kind=EvidenceKind.HTTP_HEADER,
                        source="security.scoring.rules",
                        excerpt=(
                            f"{band.value}: {percentage}% "
                            f"({total_awarded}/{total_applicable} points)"
                        ),
                    )
                ],
                details={"band": band.value, "rules_evaluated": len(rule_results)},
            )
        ]

        return AnalyzerOutput(
            findings=findings,
            data=SecurityPayload(score=score),
        )
