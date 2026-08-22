"""AI Intelligence fallback endpoint.

The user explicitly triggers this after a normal scan when evidence quality is insufficient.
AI is NOT automatic — the user must choose to run it. This endpoint:

1. Retrieves the existing scan result
2. Runs public research (if a search provider is configured)
3. Runs AI inference over existing evidence + research for the requested sections
4. Returns an enhanced result with AI findings merged in (clearly marked as AI_INFERRED)

AI findings NEVER overwrite deterministic findings. They fill gaps.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from weblens.api.deps import ScanServiceDep, SettingsDep
from weblens.domain.enums import SectionKey
from weblens.domain.errors import AiDisabledError, ScanNotFoundError
from weblens.domain.quality import EvidenceQuality, ScanQuality
from weblens.logging import get_logger
from weblens.utils.ids import is_ulid

logger = get_logger(__name__)

router = APIRouter(prefix="/scans", tags=["intelligence"])


class IntelligenceRequest(BaseModel):
    """Request body for the AI intelligence fallback."""

    model_config = ConfigDict(extra="forbid")

    sections: list[SectionKey] | None = Field(
        default=None,
        description="Sections to enhance with AI. None means all sections where AI is recommended.",
    )
    additional_context: str | None = Field(
        default=None,
        max_length=5000,
        description=(
            "Optional user-provided public context "
            "(engineering blog URLs, GitHub repos, etc.)"
        ),
    )


class IntelligenceStatus(BaseModel):
    """Status of the AI intelligence run."""

    model_config = ConfigDict(extra="forbid")

    available: bool = Field(description="Whether AI intelligence is configured and available.")
    research_available: bool = Field(description="Whether a search provider is configured.")
    inference_available: bool = Field(description="Whether an AI inference provider is configured.")
    reason: str | None = Field(
        default=None, description="Explanation when AI is not available."
    )


class IntelligenceResponse(BaseModel):
    """Response from the AI intelligence fallback."""

    model_config = ConfigDict(extra="forbid")

    scan_id: str
    mode: str = Field(
        default="ai_intelligence_fallback",
        description="Analysis mode. Always 'ai_intelligence_fallback' for this endpoint.",
    )
    sections_enhanced: list[SectionKey]
    research_performed: bool
    research_available: bool
    findings_added: int
    quality_before: ScanQuality | None = None
    quality_after: ScanQuality | None = None
    limitations: list[str] = Field(default_factory=list)


@router.get(
    "/{scan_id}/intelligence/status",
    response_model=IntelligenceStatus,
    summary="Check if AI intelligence fallback is available",
)
async def intelligence_status(
    scan_id: str, settings: SettingsDep, service: ScanServiceDep
) -> IntelligenceStatus:
    """Check whether AI intelligence can be triggered for this scan.

    Returns availability information without spending any API credits.
    """
    _validate_id(scan_id)
    # Verify the scan exists and has a result
    await service.result(scan_id)

    research_available = settings.search_provider != "none"
    inference_available = settings.inference_provider != "none"
    available = research_available or inference_available

    reason = None
    if not available:
        reason = (
            "No AI provider is configured. Set WEBLENS_SEARCH_PROVIDER and/or "
            "WEBLENS_INFERENCE_PROVIDER in your environment to enable AI intelligence."
        )

    return IntelligenceStatus(
        available=available,
        research_available=research_available,
        inference_available=inference_available,
        reason=reason,
    )


@router.post(
    "/{scan_id}/intelligence",
    response_model=IntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Run AI intelligence fallback on an existing scan",
    responses={
        501: {"description": "No AI provider is configured."},
        409: {"description": "The scan has not finished yet."},
    },
)
async def run_intelligence(
    scan_id: str,
    request: IntelligenceRequest,
    settings: SettingsDep,
    service: ScanServiceDep,
) -> IntelligenceResponse:
    """Trigger AI intelligence for sections with insufficient evidence.

    This endpoint is user-initiated and never runs automatically. It:
    1. Reads the existing deterministic scan result
    2. Runs public web research (if a search provider is configured)
    3. Runs AI inference to fill gaps in the specified sections
    4. Updates the stored result with AI-inferred findings (clearly marked)

    AI findings NEVER overwrite or modify verified/deterministic findings.
    """
    _validate_id(scan_id)

    research_available = settings.search_provider != "none"
    inference_available = settings.inference_provider != "none"

    if not research_available and not inference_available:
        raise AiDisabledError(
            "No AI provider is configured. Set WEBLENS_SEARCH_PROVIDER and/or "
            "WEBLENS_INFERENCE_PROVIDER to enable AI intelligence."
        )

    # Get existing result
    result = await service.result(scan_id)
    quality_before = result.quality

    # Determine which sections to enhance
    if request.sections:
        target_sections = request.sections
    elif quality_before and quality_before.ai_fallback_sections:
        target_sections = quality_before.ai_fallback_sections
    else:
        # Enhance all sections below MEDIUM quality
        target_sections = [
            key
            for key in SectionKey
            if quality_before
            and quality_before.sections.get(key)
            and quality_before.sections[key].quality
            in (EvidenceQuality.LOW, EvidenceQuality.FAILED)
        ]
        if not target_sections:
            target_sections = list(SectionKey)

    # Run AI intelligence pipeline via the service
    enhanced_result, findings_added = await service.run_intelligence(
        scan_id=scan_id,
        sections=target_sections,
        additional_context=request.additional_context,
    )

    quality_after = enhanced_result.quality

    limitations = [
        "AI-inferred findings are hypotheses based on "
        "observable evidence and public research.",
        "AI findings never carry 'verified' status — "
        "they are always marked as 'ai_inferred'.",
        "Private backend technologies, databases, and internal "
        "architectures cannot be determined from public observation.",
    ]
    if not research_available:
        limitations.append(
            "No search provider was configured. AI reasoning was "
            "based solely on existing scan evidence."
        )

    return IntelligenceResponse(
        scan_id=scan_id,
        sections_enhanced=target_sections,
        research_performed=research_available,
        research_available=research_available,
        findings_added=findings_added,
        quality_before=quality_before,
        quality_after=quality_after,
        limitations=limitations,
    )


def _validate_id(scan_id: str) -> None:
    if not is_ulid(scan_id):
        raise ScanNotFoundError(f"'{scan_id}' is not a valid scan id.")
