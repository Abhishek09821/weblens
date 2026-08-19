"""Health and readiness."""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from weblens.api.deps import JobStoreDep
from weblens.collection.browser import browser_status
from weblens.version import ENGINE_VERSION, SCHEMA_VERSION

router = APIRouter(tags=["meta"])

_STARTED_AT = time.monotonic()


class BrowserHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    name: str | None = None
    version: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    engine_version: str
    schema_version: str
    uptime_seconds: float
    browser: BrowserHealth
    active_scans: int


@router.get("/health", response_model=HealthResponse, summary="Liveness and browser readiness")
async def health(store: JobStoreDep) -> HealthResponse:
    """Report service liveness and whether a browser is available.

    ``status`` stays ``ok`` when the browser is missing: the API is up and HTTP-only scans still
    work. The frontend uses ``browser.available`` to warn before a scan instead of after.
    """
    status = await browser_status()
    return HealthResponse(
        status="ok",
        engine_version=ENGINE_VERSION,
        schema_version=SCHEMA_VERSION,
        uptime_seconds=round(time.monotonic() - _STARTED_AT, 2),
        browser=BrowserHealth(
            available=status.available,
            name=status.name,
            version=status.version,
            detail=status.detail,
        ),
        active_scans=await store.active_count(),
    )
