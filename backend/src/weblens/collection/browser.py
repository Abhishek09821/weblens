"""Playwright browser availability.

Phase 0 only answers "could we launch a browser if we needed one?", which ``/health`` reports so
the frontend can warn before a scan rather than after. Launching, contexts, navigation, and the
in-page probes land in Phase 1 (docs/blueprint/13-development-phases.md).

Availability is determined by looking for the downloaded browser executable, not by launching
one: a health check that starts Chromium on every poll would be a self-inflicted denial of
service. The result is cached briefly so repeated polls are free while still noticing an install
that happened after startup.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

from weblens.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 30.0
INSTALL_HINT = "Chromium is not installed. Run: python -m playwright install chromium"


@dataclass(frozen=True)
class BrowserStatus:
    available: bool
    name: str | None = None
    version: str | None = None
    detail: str | None = None


_cache: tuple[float, BrowserStatus] | None = None


async def browser_status() -> BrowserStatus:
    """Report whether a Chromium build is installed for Playwright to drive.

    ``version`` stays ``None`` until Phase 1: the exact build version is only knowable by
    launching the browser, and reporting a guess here would be the kind of invented detail this
    project exists to avoid.
    """
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]

    status = await _probe()
    _cache = (now, status)
    return status


async def _probe() -> BrowserStatus:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        return BrowserStatus(available=False, name="chromium", detail=f"playwright missing: {exc}")

    try:
        async with async_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
    except Exception as exc:
        return BrowserStatus(available=False, name="chromium", detail=str(exc)[:200])

    # A stat call can block on a network filesystem; keep it off the event loop.
    if not await asyncio.to_thread(executable.exists):
        return BrowserStatus(available=False, name="chromium", detail=INSTALL_HINT)
    return BrowserStatus(available=True, name="chromium")


def reset_cache() -> None:
    """Clear the memoized status. Used by tests."""
    global _cache
    _cache = None
