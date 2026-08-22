"""Verdict engine.

Every important AI conclusion must receive a structured verdict. This module defines
the verdict taxonomy, maps it to FindingStatus, and provides the structured output
format that reports render.

Verdict categories:
- VERIFIED: Direct evidence confirms the claim (only for deterministic findings, never AI)
- STRONGLY_SUPPORTED: Multiple independent evidence sources strongly support the claim
- LIKELY: The claim is more likely than alternatives but remains uncertain
- POSSIBLE: The claim is plausible but evidence is weak
- NOT_DETECTED: The relevant technology/signature was checked for and not observed
- NOT_PUBLICLY_DETERMINABLE: The information is likely internal/private
- UNABLE_TO_VERIFY: Insufficient evidence or research to evaluate the claim
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.enums import Confidence, FindingStatus


class VerdictCategory(StrEnum):
    """The verdict taxonomy for AI-produced conclusions."""

    VERIFIED = "verified"
    """Direct evidence confirms the claim. AI cannot produce this — only deterministic analysis."""

    STRONGLY_SUPPORTED = "strongly_supported"
    """Multiple independent evidence sources strongly support the claim."""

    LIKELY = "likely"
    """The claim is more likely than alternatives but remains uncertain."""

    POSSIBLE = "possible"
    """The claim is plausible but evidence is weak."""

    NOT_DETECTED = "not_detected"
    """The relevant technology/signature was checked for and not observed."""

    NOT_PUBLICLY_DETERMINABLE = "not_publicly_determinable"
    """The information is likely internal/private and cannot be established from public evidence."""

    UNABLE_TO_VERIFY = "unable_to_verify"
    """The system could not collect enough evidence or research to evaluate the claim."""


class VerdictSource(BaseModel):
    """One source backing a verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(description="Human-readable source description.")
    url: str | None = Field(default=None, description="URL if available.")
    source_type: str = Field(
        default="evidence", description="Type: evidence, research, observation."
    )
    reliability: str = Field(
        default="medium", description="high, medium, low."
    )


class Verdict(BaseModel):
    """A structured AI verdict for one claim.

    This is the output format that reports render. Every AI conclusion
    must be expressed as a Verdict before it appears in a report.
    """

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(description="The technology/architecture assertion.")
    category: VerdictCategory
    confidence: int = Field(
        ge=0, le=100, description="Confidence percentage reflecting evidence quality."
    )
    hypothesis: str = Field(
        default="", description="Extended explanation of the claim."
    )
    basis: list[str] = Field(
        default_factory=list,
        description="Evidence items that support this verdict.",
    )
    sources: list[VerdictSource] = Field(
        default_factory=list,
        description="Provenance sources with URLs and reliability.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="What cannot be determined or verified about this claim.",
    )
    section: str = Field(
        default="technology",
        description="Which report section this verdict belongs to.",
    )


# --- Mapping functions -----------------------------------------------------------------


def verdict_to_finding_status(verdict: VerdictCategory) -> FindingStatus:
    """Map a verdict category to the FindingStatus used in the domain model.

    AI can never produce VERIFIED — that's reserved for direct deterministic observation.
    """
    mapping: dict[VerdictCategory, FindingStatus] = {
        VerdictCategory.VERIFIED: FindingStatus.VERIFIED,  # Never produced by AI
        VerdictCategory.STRONGLY_SUPPORTED: FindingStatus.AI_INFERRED,
        VerdictCategory.LIKELY: FindingStatus.AI_INFERRED,
        VerdictCategory.POSSIBLE: FindingStatus.AI_INFERRED,
        VerdictCategory.NOT_DETECTED: FindingStatus.NOT_DETECTED,
        VerdictCategory.NOT_PUBLICLY_DETERMINABLE: FindingStatus.NOT_DETERMINABLE,
        VerdictCategory.UNABLE_TO_VERIFY: FindingStatus.UNABLE_TO_VERIFY,
    }
    return mapping[verdict]


def verdict_to_confidence(verdict: VerdictCategory, score: int) -> Confidence:
    """Map verdict + numeric confidence to the internal Confidence enum."""
    if verdict == VerdictCategory.STRONGLY_SUPPORTED and score >= 75:
        return Confidence.STRONG
    if verdict == VerdictCategory.LIKELY and score >= 50:
        return Confidence.MODERATE
    if verdict in (VerdictCategory.POSSIBLE, VerdictCategory.LIKELY) and score < 50:
        return Confidence.WEAK
    if score >= 70:
        return Confidence.STRONG
    if score >= 40:
        return Confidence.MODERATE
    return Confidence.WEAK


def confidence_reflects_evidence(verdict: Verdict) -> bool:
    """Validate that the confidence score is consistent with the evidence basis.

    A high confidence with no basis is suspicious. This is a sanity check, not a gate.
    """
    if verdict.confidence > 80 and len(verdict.basis) < 2:
        return False
    return not (verdict.confidence > 60 and len(verdict.basis) == 0)


def cap_confidence(verdict: Verdict) -> Verdict:
    """Cap confidence if it exceeds what the evidence basis supports.

    This prevents the LLM from outputting '95% confidence' when it has minimal basis.
    """
    if not confidence_reflects_evidence(verdict):
        max_confidence = min(verdict.confidence, 30 + len(verdict.basis) * 15)
        return verdict.model_copy(update={"confidence": max_confidence})
    return verdict
