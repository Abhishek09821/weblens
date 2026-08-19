"""Health, capabilities, and the committed contract."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from tests.conftest import FakeCollector
from weblens.orchestration import registry
from weblens.version import ENGINE_VERSION, SCHEMA_VERSION

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "openapi.json"


async def test_health(api_client: tuple[httpx.AsyncClient, FakeCollector]) -> None:
    client, _ = api_client
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["engine_version"] == ENGINE_VERSION
    assert body["schema_version"] == SCHEMA_VERSION
    assert "available" in body["browser"]


async def test_health_is_ok_even_without_a_browser(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    """The API is up whether or not Chromium is installed; HTTP-only scans still work.

    The frontend uses ``browser.available`` for a pre-flight warning, so this must not be
    conflated with liveness.
    """
    client, _ = api_client
    body = (await client.get("/health")).json()
    assert body["status"] == "ok"
    if not body["browser"]["available"]:
        assert body["browser"]["detail"]


async def test_capabilities_lists_every_declared_analyzer(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    body = (await client.get("/api/v1/capabilities")).json()

    assert len(body["sections"]) == 8
    assert len(body["analyzers"]) == len(registry.all_entries())

    implemented = [entry["id"] for entry in body["analyzers"] if entry["implemented"]]
    assert implemented == ["seo.metadata"]

    unimplemented = [entry for entry in body["analyzers"] if not entry["implemented"]]
    assert unimplemented, "phased development must be visible to the client"
    assert all(entry["planned_phase"] > 0 for entry in unimplemented)
    assert all(entry["description"] for entry in body["analyzers"])


async def test_capabilities_reports_stage_implementation_state(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    body = (await client.get("/api/v1/capabilities")).json()
    stages = {stage["key"]: stage for stage in body["stages"]}
    assert stages["http_probe"]["implemented"] is True
    assert stages["a11y_capture"]["implemented"] is False
    assert stages["http_probe"]["optional"] is False


async def test_capabilities_exposes_limits(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    limits = (await client.get("/api/v1/capabilities")).json()["limits"]
    assert limits["respect_robots"] is True
    assert limits["total_scan_budget_ms"] > 0
    assert limits["result_ttl_seconds"] > 0


async def test_committed_contract_matches_the_app(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    """Contract drift is a build error, not a runtime surprise.

    ``contracts/openapi.json`` is what the frontend types are generated from, so a backend change
    that is not exported here would silently desynchronize the two sides.
    """
    client, _ = api_client
    live = (await client.get("/openapi.json")).json()
    committed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert live == committed, "contracts/openapi.json is out of date. Run: make contracts"
