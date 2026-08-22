"""Capabilities: what this build can actually do.

The frontend renders section states from this rather than hardcoding assumptions, so an
analyzer that has not been built yet shows up as "not implemented in this build" instead of an
empty panel that looks like a finding of "nothing found".
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from weblens.ai.inference import get_inference_provider
from weblens.analyzers.traffic.provider import get_traffic_provider
from weblens.api.deps import SettingsDep
from weblens.domain.enums import SectionKey
from weblens.orchestration import registry
from weblens.orchestration.stages import STAGES
from weblens.research.base import get_provider as get_search_provider
from weblens.version import ENGINE_VERSION, SCHEMA_VERSION

router = APIRouter(tags=["meta"])


class AnalyzerCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    section: SectionKey
    version: str
    description: str
    implemented: bool
    requires: list[str]
    depends_on: list[str]
    planned_phase: int


class StageCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    weight: int
    implemented: bool
    optional: bool


class ScanLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    navigation_timeout_ms: int
    total_scan_budget_ms: int
    analyzer_timeout_ms: int
    result_ttl_seconds: int
    max_concurrent_scans: int
    max_concurrent_scans_per_host: int
    min_host_interval_seconds: float
    max_redirects: int
    respect_robots: bool
    probe_http_downgrade: bool


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: str
    schema_version: str
    collection_mode: str
    sections: list[SectionKey]
    analyzers: list[AnalyzerCapability]
    stages: list[StageCapability]
    limits: ScanLimits
    research_available: bool
    inference_available: bool
    traffic_provider_available: bool


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="Analyzers, stages, and limits in this build",
)
async def capabilities(settings: SettingsDep) -> CapabilitiesResponse:
    return CapabilitiesResponse(
        engine_version=ENGINE_VERSION,
        schema_version=SCHEMA_VERSION,
        collection_mode="http_only",
        sections=list(SectionKey),
        analyzers=[
            AnalyzerCapability(
                id=entry.id,
                section=entry.section,
                version=entry.version,
                description=entry.description,
                implemented=entry.implemented,
                requires=sorted(slot.value for slot in entry.requires),
                depends_on=sorted(entry.depends_on),
                planned_phase=entry.phase,
            )
            for entry in registry.all_entries()
        ],
        stages=[
            StageCapability(
                key=stage.key.value,
                label=stage.label,
                weight=stage.weight,
                implemented=stage.implemented,
                optional=stage.optional,
            )
            for stage in STAGES
        ],
        limits=ScanLimits(
            navigation_timeout_ms=settings.navigation_timeout_ms,
            total_scan_budget_ms=settings.total_scan_budget_ms,
            analyzer_timeout_ms=settings.analyzer_timeout_ms,
            result_ttl_seconds=settings.result_ttl_seconds,
            max_concurrent_scans=settings.max_concurrent_scans,
            max_concurrent_scans_per_host=settings.max_concurrent_scans_per_host,
            min_host_interval_seconds=settings.min_host_interval_seconds,
            max_redirects=settings.max_redirects,
            respect_robots=settings.respect_robots,
            probe_http_downgrade=settings.probe_http_downgrade,
        ),
        research_available=get_search_provider(settings.search_provider).is_available,
        inference_available=get_inference_provider(settings.inference_provider).is_available,
        traffic_provider_available=get_traffic_provider(settings.traffic_provider).is_available,
    )
