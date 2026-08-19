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
