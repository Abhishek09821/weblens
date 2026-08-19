"""Security posture score models.

The score exists because presence and quality of observable defensive configuration is
genuinely useful to communicate. It is bounded by two design choices encoded here:

* every rule result carries its own ``rationale`` and evidence, so the number is auditable;
* ``excluded_rules`` records what was left out of the ratio and why, so the denominator is
  auditable too.

Scoring logic lives in ``analyzers/security/``. This module only defines the shapes.
Methodology: docs/blueprint/11-security-scoring-methodology.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.enums import PostureBand, RuleOutcome, SecurityCategory
from weblens.domain.evidence import EvidenceRef

POSTURE_LABEL = "Observable Security Posture"

POSTURE_DISCLAIMER = (
    "This is a passive assessment of externally observable configuration for a single page "
    "at a single point in time. It does not evaluate application logic, server-side "
    "controls, dependencies, or data handling, and it cannot establish that a site is "
    "secure or insecure."
)

BAND_PHRASING: dict[PostureBand, str] = {
    PostureBand.STRONG: "Strong observable posture",
    PostureBand.GOOD: "Good observable posture",
    PostureBand.MODERATE: "Moderate observable posture",
    PostureBand.LIMITED: "Limited observable posture",
    PostureBand.MINIMAL: "Minimal observable posture",
}


class SecurityRuleResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Stable rule id, e.g. 'HDR-01'.")
    title: str
    category: SecurityCategory
    outcome: RuleOutcome
    weight: float = Field(description="Points available when the rule is applicable.")
    awarded: float = Field(description="Points earned, between 0 and weight.")
    rationale: str = Field(description="Why this outcome, stated in observable terms.")
    evidence: list[EvidenceRef] = Field(default_factory=list)
    recommendation: str | None = None
    reference: str | None = Field(default=None, description="Specification or documentation URL.")


class ExcludedRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    outcome: RuleOutcome = Field(description="Either not_applicable or unknown.")
    reason: str


class AppliedCap(BaseModel):
    """A band ceiling triggered by a dominant observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    cap: PostureBand
    reason: str


class SecurityScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    methodology_version: str
    points_awarded: float
    points_applicable: float = Field(
        description="Sum of weights for evaluated rules only; excluded rules are not counted."
    )
    percentage: float
    band: PostureBand
    band_phrase: str
    label: str = POSTURE_LABEL
    disclaimer: str = POSTURE_DISCLAIMER
    rules: list[SecurityRuleResult] = Field(default_factory=list)
    excluded_rules: list[ExcludedRule] = Field(default_factory=list)
    applied_caps: list[AppliedCap] = Field(default_factory=list)
