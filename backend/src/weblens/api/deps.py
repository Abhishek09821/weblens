"""Dependency wiring.

Components are built once in the application lifespan and stored on ``app.state``. Routes read
them through these accessors, which keeps construction in one place and makes substitution in
tests a one-line override (a fake collector, a stub guard) rather than a monkeypatch.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from weblens.config import Settings
from weblens.orchestration.job_store import InMemoryJobStore
from weblens.orchestration.service import ScanService


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_scan_service(request: Request) -> ScanService:
    service: ScanService = request.app.state.scan_service
    return service


def get_job_store(request: Request) -> InMemoryJobStore:
    store: InMemoryJobStore = request.app.state.job_store
    return store


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ScanServiceDep = Annotated[ScanService, Depends(get_scan_service)]
JobStoreDep = Annotated[InMemoryJobStore, Depends(get_job_store)]
