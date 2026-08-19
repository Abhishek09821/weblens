"""Application factory and lifespan.

Components are constructed once here and attached to ``app.state``, which keeps wiring in one
readable place and lets tests swap the collector or the guard by overriding a single attribute.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from weblens.api.problems import register_exception_handlers
from weblens.api.router import api_router, root_router
from weblens.collection.base import Collector
from weblens.collection.http_collector import HttpEvidenceCollector
from weblens.collection.target import TargetGuard
from weblens.config import Settings, get_settings
from weblens.logging import configure_logging, get_logger
from weblens.orchestration import registry
from weblens.orchestration.job_store import InMemoryJobStore, periodic_sweep
from weblens.orchestration.service import ScanService
from weblens.version import ENGINE_VERSION

logger = get_logger(__name__)

DESCRIPTION = """
Evidence-based website technical intelligence.

Detection is deterministic and never performed by an AI model. Every asserted fact carries the
evidence that supports it, and anything that cannot be established from observation is reported
as not detected, not determinable, or unable to verify rather than guessed.

Analysis is passive: WebLens observes what a normal visit reveals. It does not test
authentication, submit forms, fuzz inputs, or attempt to bypass access controls.
""".strip()


def create_app(
    settings: Settings | None = None,
    collector: Collector | None = None,
    guard: TargetGuard | None = None,
) -> FastAPI:
    """Build the application.

    ``collector`` and ``guard`` are injection seams for tests: a fake collector plus a guard with
    a stubbed resolver let the whole pipeline and API be exercised with no network at all.
    Production callers omit both and get :class:`HttpEvidenceCollector` with a real resolver.
    """
    resolved = settings or get_settings()
    configure_logging(level=resolved.log_level, fmt=resolved.log_format)
    registry.validate_registry()

    app = FastAPI(
        title="WebLens API",
        version=ENGINE_VERSION,
        description=DESCRIPTION,
        lifespan=_lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )
    app.state.settings = resolved
    app.state.collector_override = collector
    app.state.guard_override = guard

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    register_exception_handlers(app)
    app.include_router(root_router)
    app.include_router(api_router)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    guard: TargetGuard = getattr(app.state, "guard_override", None) or TargetGuard(settings)
    store = InMemoryJobStore(settings)
    override: Collector | None = getattr(app.state, "collector_override", None)
    collector: Collector = override or HttpEvidenceCollector(settings, guard)

    app.state.target_guard = guard
    app.state.job_store = store
    app.state.collector = collector
    app.state.scan_service = ScanService(settings, store, guard, collector)

    sweeper = asyncio.create_task(periodic_sweep(store), name="weblens-job-sweeper")
    implemented = sum(1 for entry in registry.all_entries() if entry.implemented)
    logger.info(
        "weblens started",
        extra={
            "engine_version": ENGINE_VERSION,
            "analyzers_implemented": implemented,
            "analyzers_declared": len(registry.all_entries()),
            "collection_mode": collector.collection_mode,
        },
    )
    if settings.allow_private_targets:
        logger.warning(
            "allow_private_targets is enabled: the API will scan loopback and private addresses. "
            "This is a test-only setting."
        )

    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper
        logger.info("weblens stopped")


app = create_app()
