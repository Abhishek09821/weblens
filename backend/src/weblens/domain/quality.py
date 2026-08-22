"""Evidence quality gate.

After the normal scan, each section receives a quality band that communicates how much
useful evidence was produced. The overall scan quality is the minimum of the four section
qualities — a scan is only as strong as its weakest section.

The quality band determines whether an AI fallback is offered to the user:
- HIGH / MEDIUM: Normal reports are sufficient. AI is not required.
- LOW: Reports can be produced but are thin. AI fallback is offered.
- FAILED: The section could not meaningfully produce output. AI fallback is strongly recommended.

Quality is calculated from:
- Ratio of completed vs total analyzers for that section
- Count and status distribution of findings (verified > inferred > unknown)
- Whether critical evidence was available (e.g., browser collection for design)
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from weblens.domain.enums import AnalyzerRunStatus, FindingStatus, SectionKey, SectionStatus
from weblens.domain.sections import Section, SectionSet


class EvidenceQuality(StrEnum):
    """Quality band for a section or the overall scan."""

    HIGH = "high"
    """Sufficient evidence for a comprehensive report without AI assistance."""

    MEDIUM = "medium"
    """Reasonable evidence. Some gaps exist but the report is useful."""

    LOW = "low"
    """Thin evidence. Key areas lack data. AI fallback is recommended."""

    FAILED = "failed"
    """Insufficient evidence to produce a meaningful report."""


class SectionQuality(BaseModel):
    """Quality assessment for one section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    section: SectionKey
    quality: EvidenceQuality
    score: int = Field(ge=0, le=100, description="Numeric score 0-100.")
    analyzers_completed: int
    analyzers_total: int
    findings_verified: int
    findings_inferred: int
    findings_negative: int
    ai_fallback_recommended: bool
    reason: str = Field(
        description="Human-readable explanation of the quality assessment."
    )


class ScanQuality(BaseModel):
    """Overall scan quality assessment across all four sections."""

    model_config = ConfigDict(extra="forbid")

    overall: EvidenceQuality
    overall_score: int = Field(ge=0, le=100)
    sections: dict[SectionKey, SectionQuality]
    ai_fallback_available: bool = Field(
        description="Whether at least one section would benefit from AI fallback."
    )
    ai_fallback_sections: list[SectionKey] = Field(
        default_factory=list,
        description="Sections where AI fallback is recommended.",
    )


def assess_quality(sections: SectionSet) -> ScanQuality:
    """Calculate evidence quality for the completed scan."""
    section_qualities: dict[SectionKey, SectionQuality] = {}

    for key in SectionKey:
        section = getattr(sections, key.value)
        section_qualities[key] = _assess_section(key, section)

    # Overall is the weakest section
    scores = [sq.score for sq in section_qualities.values()]
    overall_score = min(scores) if scores else 0
    overall = _band_for_score(overall_score)

    fallback_sections = [
        key for key, sq in section_qualities.items() if sq.ai_fallback_recommended
    ]

    return ScanQuality(
        overall=overall,
        overall_score=overall_score,
        sections=section_qualities,
        ai_fallback_available=len(fallback_sections) > 0,
        ai_fallback_sections=fallback_sections,
    )


def _assess_section(key: SectionKey, section: Section) -> SectionQuality:  # type: ignore[type-arg]
    """Assess quality for one section."""
    meta = section.meta
    findings = section.findings

    # Analyzer completion ratio
    analyzers_total = len(meta.analyzers)
    analyzers_completed = sum(
        1 for run in meta.analyzers if run.status == AnalyzerRunStatus.COMPLETED
    )

    # Finding status distribution
    verified = sum(
        1 for f in findings
        if f.status in (FindingStatus.VERIFIED, FindingStatus.STRONGLY_INFERRED)
    )
    inferred = sum(1 for f in findings if f.status == FindingStatus.INFERRED)
    negative = sum(
        1
        for f in findings
        if f.status in (
            FindingStatus.NOT_DETECTED,
            FindingStatus.NOT_DETERMINABLE,
            FindingStatus.UNABLE_TO_VERIFY,
        )
    )

    # Section was not produced at all
    if meta.status in (
        SectionStatus.UNAVAILABLE,
        SectionStatus.NOT_IMPLEMENTED,
        SectionStatus.SKIPPED,
    ):
        return SectionQuality(
            section=key,
            quality=EvidenceQuality.FAILED,
            score=0,
            analyzers_completed=analyzers_completed,
            analyzers_total=analyzers_total,
            findings_verified=verified,
            findings_inferred=inferred,
            findings_negative=negative,
            ai_fallback_recommended=True,
            reason=meta.unavailable_reason or f"Section '{key.value}' was not produced.",
        )

    # Calculate score based on weighted factors
    score = _calculate_section_score(
        key=key,
        analyzers_completed=analyzers_completed,
        analyzers_total=analyzers_total,
        verified=verified,
        inferred=inferred,
        negative=negative,
        total_findings=len(findings),
    )

    quality = _band_for_score(score)
    ai_recommended = quality in (EvidenceQuality.LOW, EvidenceQuality.FAILED)

    reason = _quality_reason(key, quality, analyzers_completed, analyzers_total, verified, inferred)

    return SectionQuality(
        section=key,
        quality=quality,
        score=score,
        analyzers_completed=analyzers_completed,
        analyzers_total=analyzers_total,
        findings_verified=verified,
        findings_inferred=inferred,
        findings_negative=negative,
        ai_fallback_recommended=ai_recommended,
        reason=reason,
    )


def _calculate_section_score(
    *,
    key: SectionKey,
    analyzers_completed: int,
    analyzers_total: int,
    verified: int,
    inferred: int,
    negative: int,
    total_findings: int,
) -> int:
    """Calculate a 0-100 quality score for a section.

    Weighting:
    - 40% analyzer completion rate
    - 40% positive finding density (verified + inferred vs total)
    - 20% absolute evidence threshold (minimum useful findings per section)
    """
    # Analyzer completion (0-40 points)
    analyzer_score = (
        0.0 if analyzers_total == 0
        else (analyzers_completed / analyzers_total) * 40.0
    )

    # Positive finding density (0-40 points)
    positive = verified + inferred
    density_score = (
        0.0 if total_findings == 0
        else (positive / total_findings) * 40.0
    )

    # Absolute threshold (0-20 points) - minimum useful findings per section type
    threshold = _minimum_findings_threshold(key)
    if positive >= threshold:
        threshold_score = 20.0
    elif positive == 0:
        threshold_score = 0.0
    else:
        threshold_score = (positive / threshold) * 20.0

    return min(100, int(analyzer_score + density_score + threshold_score))


def _minimum_findings_threshold(key: SectionKey) -> int:
    """Minimum positive findings needed for a section to be considered adequate."""
    thresholds = {
        SectionKey.DESIGN: 8,
        SectionKey.TECHNOLOGY: 5,
        SectionKey.SECURITY: 6,
        SectionKey.TRAFFIC: 2,
    }
    return thresholds.get(key, 5)


def _band_for_score(score: int) -> EvidenceQuality:
    """Map numeric score to quality band."""
    if score >= 70:
        return EvidenceQuality.HIGH
    if score >= 40:
        return EvidenceQuality.MEDIUM
    if score >= 15:
        return EvidenceQuality.LOW
    return EvidenceQuality.FAILED


def _quality_reason(
    key: SectionKey,
    quality: EvidenceQuality,
    analyzers_completed: int,
    analyzers_total: int,
    verified: int,
    inferred: int,
) -> str:
    """Generate a human-readable explanation."""
    positive = verified + inferred
    section_name = key.value.replace("_", " ").title()

    if quality == EvidenceQuality.HIGH:
        return (
            f"{section_name}: {analyzers_completed}/{analyzers_total} analyzers completed, "
            f"{positive} verified/inferred findings. Evidence is sufficient."
        )
    if quality == EvidenceQuality.MEDIUM:
        return (
            f"{section_name}: {analyzers_completed}/{analyzers_total} analyzers completed, "
            f"{positive} verified/inferred findings. Some gaps exist."
        )
    if quality == EvidenceQuality.LOW:
        return (
            f"{section_name}: {analyzers_completed}/{analyzers_total} analyzers completed, "
            f"only {positive} verified/inferred findings. "
            "AI intelligence could supplement the analysis."
        )
    return (
        f"{section_name}: {analyzers_completed}/{analyzers_total} analyzers completed, "
        f"only {positive} verified/inferred findings. "
        "Evidence is insufficient for a meaningful report."
    )
