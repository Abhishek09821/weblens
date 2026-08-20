"""Optional AI explanation layer.

Disabled by default and structurally incapable of affecting detection: it runs after a scan, is
given findings only, and its output is returned separately from ``AnalysisResult`` so it can
never be mistaken for - or stored as - a verified fact.

Phase 7 implements a provider. Until then this endpoint exists to make the contract explicit
and to return an honest 501 instead of silently pretending the capability is unavailable.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from weblens.ai.provider import get_provider
from weblens.api.deps import ScanServiceDep, SettingsDep
from weblens.domain.enums import SectionKey

router = APIRouter(prefix="/ai", tags=["ai"])


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str
    sections: list[SectionKey] | None = None
    audience: str = Field(default="engineer", pattern="^(engineer|stakeholder)$")


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: SectionKey
    text: str
    grounded_in: list[str] = Field(
        description="Finding ids the text cites. Every sentence must cite at least one."
    )


class DroppedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    reason: str


class ExplainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str
    provider: str
    model: str | None = None
    generated_at: str
    narratives: list[Narrative] = Field(default_factory=list)
    dropped_claims: list[DroppedClaim] = Field(
        default_factory=list,
        description="Statements removed because they could not be traced to a finding.",
    )


@router.post(
    "/explain",
    response_model=ExplainResponse,
    summary="Generate an explanation over verified findings",
    responses={501: {"description": "No AI provider is configured."}},
)
async def explain(
    request: ExplainRequest, settings: SettingsDep, service: ScanServiceDep
) -> ExplainResponse:
    provider = get_provider(settings)
    result = await service.result(request.scan_id)
    return await provider.explain(result, request.sections, request.audience)


class SummarizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: str | None = None
    result_data: dict[str, object] | None = None


class SummarizeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    summary: str | None = None
    model: str | None = None
    disclaimer: str = (
        "This summary is AI-generated from verified analysis findings. "
        "It does not introduce new detections or modify factual values."
    )


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Generate a human-readable AI summary of the analysis",
)
async def summarize(
    request: SummarizeRequest, service: ScanServiceDep
) -> SummarizeResponse:
    from weblens.ai.summarize import (
        GROQ_MODEL,
        build_summary_input,
        generate_summary,
        is_ai_available,
    )

    if not is_ai_available():
        return SummarizeResponse(available=False, summary=None)

    # Accept either a scan_id (if still on server) or direct result_data from client
    if request.result_data:
        summary_input = build_summary_input(request.result_data)  # type: ignore[arg-type]
    elif request.scan_id:
        try:
            result = await service.result(request.scan_id)
            summary_input = build_summary_input(result.model_dump())
        except Exception:
            return SummarizeResponse(
                available=True,
                summary=None,
                model=None,
            )
    else:
        return SummarizeResponse(available=False, summary=None)

    summary_text = await generate_summary(summary_input)

    return SummarizeResponse(
        available=True,
        summary=summary_text,
        model=GROQ_MODEL if summary_text else None,
    )
