"""Shared test fixtures.

Two things make the suite fast and honest: evidence is built in-process (no network), and the
collector is injected, so the whole pipeline and API can be exercised against recorded shapes.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from weblens.collection.base import CollectionOutcome
from weblens.collection.target import NormalizedTarget, TargetGuard
from weblens.config import Settings
from weblens.domain.enums import DomSource, StageKey
from weblens.domain.evidence import RawEvidence
from weblens.domain.observations import (
    DnsObservation,
    DomObservation,
    HeaderEntry,
    HttpHopObservation,
    HttpObservation,
    RobotsObservation,
    TargetObservation,
)
from weblens.domain.scan import RunContext, ScanOptions
from weblens.main import create_app

TEST_URL = "https://example.test/"
TEST_HOST = "example.test"


@pytest.fixture
def settings() -> Settings:
    """Settings with politeness delays removed so tests do not sleep."""
    return Settings(
        min_host_interval_seconds=0.0,
        max_concurrent_scans=4,
        max_concurrent_scans_per_host=2,
        result_ttl_seconds=60,
        analyzer_timeout_ms=2000,
        log_level="CRITICAL",
    )


@pytest.fixture
def normalized_target() -> NormalizedTarget:
    return NormalizedTarget(
        requested_url=TEST_URL,
        fetch_url=TEST_URL,
        display_url=TEST_URL,
        scheme="https",
        host=TEST_HOST,
        port=443,
        path="/",
        resolved_ips=("93.184.216.34",),
    )


def make_http_observation(
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    final_url: str = TEST_URL,
) -> HttpObservation:
    header_entries = [
        HeaderEntry(name=name.lower(), value=value)
        for name, value in (headers or {"content-type": "text/html; charset=utf-8"}).items()
    ]
    return HttpObservation(
        hops=[
            HttpHopObservation(
                url=final_url, status=status, http_version="HTTP/1.1", headers=header_entries
            )
        ],
        final_url=final_url,
        status=status,
        http_version="HTTP/1.1",
        headers=header_entries,
        content_type="text/html",
        charset="utf-8",
        body_text=body,
        body_bytes=len(body.encode()) if body else 0,
        elapsed_ms=12.0,
    )


def make_dom_observation(**overrides: Any) -> DomObservation:
    defaults: dict[str, Any] = {
        "source": DomSource.STATIC_HTML,
        "title": "Example Title",
        "lang": "en",
        "charset": "utf-8",
    }
    defaults.update(overrides)
    return DomObservation(**defaults)


def make_evidence(
    *,
    http: HttpObservation | None = None,
    dom: DomObservation | None = None,
    dns: DnsObservation | None = None,
    robots: RobotsObservation | None = None,
) -> RawEvidence:
    """Build evidence with only the slots a test cares about.

    Slots left out stay ``None``, which is exactly the "not collected" state analyzers must
    handle - so the degraded path is the default in tests rather than an afterthought.
    """
    return RawEvidence(
        target=TargetObservation(
            requested_url=TEST_URL,
            normalized_url=TEST_URL,
            scheme="https",
            host=TEST_HOST,
            port=443,
            path="/",
        ),
        http=http,
        dom=dom,
        dns=dns,
        robots=robots,
    )


@pytest.fixture
def sample_evidence() -> RawEvidence:
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Sample Page</title>
<meta name="description" content="A sample page used in tests.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Sample Page">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="https://example.test/">
<link rel="icon" href="/favicon.ico">
<link rel="alternate" hreflang="de" href="https://example.test/de">
</head><body><h1>Sample Page</h1><p>Body copy.</p></body></html>"""
    from weblens.collection.static_html import parse_static_html

    return make_evidence(
        http=make_http_observation(body=html),
        dom=parse_static_html(html, TEST_URL),
        dns=DnsObservation(host=TEST_HOST, resolved_ips=["93.184.216.34"]),
        robots=RobotsObservation(
            url="https://example.test/robots.txt", fetched=True, status=404, allowed=True
        ),
    )


class FakeCollector:
    """Collector that replays prepared evidence instead of making requests."""

    collection_mode = "fake"

    def __init__(self, evidence: RawEvidence, *, error: Exception | None = None) -> None:
        self._evidence = evidence
        self._error = error
        self.calls = 0

    async def collect(
        self, target: NormalizedTarget, options: ScanOptions, sink: Any
    ) -> CollectionOutcome:
        self.calls += 1
        await sink.stage_started(StageKey.HTTP_PROBE)
        if self._error is not None:
            await sink.stage_failed(
                StageKey.HTTP_PROBE,
                getattr(self._error, "code", None) or "CONNECT_FAILURE",  # type: ignore[arg-type]
                str(self._error),
            )
            raise self._error
        await sink.stage_completed(StageKey.HTTP_PROBE)
        return CollectionOutcome(
            evidence=self._evidence,
            redirect_chain=[],
            run_context=RunContext(
                wait_strategy="fixture",
                collection_mode=self.collection_mode,
                viewport=options.viewport,
            ),
        )


class StubResolver:
    """DNS resolver stub so guard tests run offline and deterministically."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping

    async def resolve(self, host: str) -> list[str]:
        if host not in self._mapping:
            raise OSError(f"stub resolver has no entry for {host}")
        return self._mapping[host]


#: ``.test`` is a reserved TLD that never resolves, which is exactly what we want in tests: the
#: real guard still runs (so its rejections are exercised) but no DNS query leaves the machine.
TEST_RESOLUTIONS = {
    TEST_HOST: ["93.184.216.34"],
    "other.test": ["93.184.216.35"],
    "blocked.test": ["127.0.0.1"],
}


def make_test_guard(settings: Settings) -> TargetGuard:
    return TargetGuard(settings, resolver=StubResolver(TEST_RESOLUTIONS))


@pytest.fixture
async def api_client(
    settings: Settings, sample_evidence: RawEvidence
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeCollector]]:
    """App wired with a fake collector and a stubbed resolver: no sockets, no network."""
    collector = FakeCollector(sample_evidence)
    async with build_client(settings, collector) as pair:
        yield pair


@asynccontextmanager
async def build_client(
    settings: Settings, collector: FakeCollector
) -> AsyncIterator[tuple[httpx.AsyncClient, FakeCollector]]:
    """Shared app/client construction for tests that need their own wiring."""
    app = create_app(settings=settings, collector=collector, guard=make_test_guard(settings))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://weblens.test") as client:
            yield client, collector


@pytest.fixture(scope="session")
def live_enabled() -> bool:
    return os.environ.get("WEBLENS_LIVE") == "1"


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> Iterator[None]:
    """Keep the cached settings singleton from leaking between tests."""
    from weblens.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
