"""API router composition."""

from __future__ import annotations

from fastapi import APIRouter

from weblens.api.routes import ai, capabilities, health, scans

API_V1_PREFIX = "/api/v1"

# /health sits outside the versioned prefix: liveness checks should not have to track API
# versions.
root_router = APIRouter()
root_router.include_router(health.router)

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(capabilities.router)
api_router.include_router(scans.router)
api_router.include_router(ai.router)
