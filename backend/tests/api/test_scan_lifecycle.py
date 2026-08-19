"""API lifecycle and failure-isolation tests.

Runs the whole pipeline over injected evidence: no sockets, no browser, no network.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from tests.conftest import FakeCollector, build_client, make_evidence, make_http_observation
from weblens.analyzers.base import AnalyzerContext, AnalyzerOutput
from weblens.config import Settings
from weblens.domain.enums import EvidenceSlot, SectionKey
from weblens.domain.errors import ConnectFailureError
from weblens.orchestration import registry
from weblens.orchestration.registry import AnalyzerEntry

TERMINAL = {"completed", "completed_with_errors", "failed", "cancelled"}


async def wait_for_terminal(client: httpx.AsyncClient, scan_id: str) -> dict[str, Any]:
    for _ in range(200):
        response = await client.get(f"/api/v1/scans/{scan_id}")
        response.raise_for_status()
        state = response.json()
        if state["status"] in TERMINAL:
            return state
        await asyncio.sleep(0.01)
    raise AssertionError("scan did not reach a terminal state")


async def submit(client: httpx.AsyncClient, url: str = "https://example.test/") -> str:
    response = await client.post("/api/v1/scans", json={"url": url})
    assert response.status_code == 202, response.text
    return str(response.json()["scan_id"])


# --- happy path -------------------------------------------------------------------------


async def test_full_lifecycle(api_client: tuple[httpx.AsyncClient, FakeCollector]) -> None:
    client, collector = api_client

    scan_id = await submit(client)
    state = await wait_for_terminal(client, scan_id)
    # Some analyzers require evidence slots the fake collector doesn't provide (runtime,
    # styles, network), resulting in partial sections. This is expected behavior.
    assert state["status"] in ("completed", "completed_with_errors")
    assert collector.calls == 1

    result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()
    assert result["schema_version"] == "1.0"
    assert result["target"]["host"] == "example.test"
    assert result["sections"]["seo"]["meta"]["status"] == "complete"
    assert len(result["sections"]["seo"]["findings"]) >= 11

    deleted = await client.delete(f"/api/v1/scans/{scan_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/scans/{scan_id}")).status_code == 404


async def test_progress_reaches_full_weight(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    """Progress must complete, not stall - it is derived from real stage completions."""
    client, _ = api_client
    scan_id = await submit(client)
    state = await wait_for_terminal(client, scan_id)
    progress = state["progress"]
    assert progress["completed_weight"] == progress["total_weight"]
    assert progress["stages_completed"] == progress["stages_total"]
    assert progress["current_stage"] is None


async def test_unimplemented_sections_are_reported_honestly(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    scan_id = await submit(client)
    await wait_for_terminal(client, scan_id)
    result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()

    # With only HTTP+DOM evidence from the fake collector, sections that need
    # runtime/styles/network/performance will be unavailable or partial.
    # Security headers section should work (only needs HTTP).
    sec = result["sections"]["security"]
    assert sec["meta"]["status"] in ("complete", "partial")
    assert len(sec["findings"]) > 0

    # SEO should be complete (needs only HTTP + DOM + ROBOTS)
    seo = result["sections"]["seo"]
    assert seo["meta"]["status"] == "complete"

    # Design needs STYLES which the fake collector doesn't provide
    design = result["sections"]["design"]
    assert design["meta"]["status"] in ("unavailable", "partial")

    # Every section has analyzers metadata
    for key in ("design", "technology", "security", "performance", "accessibility", "network"):
        section = result["sections"][key]
        assert section["meta"]["analyzers"]


async def test_result_carries_scan_wide_limitations(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    scan_id = await submit(client)
    await wait_for_terminal(client, scan_id)
    result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()
    assert any("No crawling" in item for item in result["limitations"])
    assert result["scan"]["run_context"]["collection_mode"] == "fake"


async def test_sse_stream_emits_stages_and_terminates(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    scan_id = await submit(client)

    events: list[str] = []
    async with client.stream("GET", f"/api/v1/scans/{scan_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                events.append(line.removeprefix("event: ").strip())
            if events and events[-1] in ("done", "error"):
                break

    assert events[0] == "snapshot"
    assert events[-1] == "done"


async def test_sections_can_be_restricted(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    response = await client.post(
        "/api/v1/scans", json={"url": "https://example.test/", "options": {"sections": ["seo"]}}
    )
    scan_id = response.json()["scan_id"]
    await wait_for_terminal(client, scan_id)
    result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()
    assert result["sections"]["seo"]["meta"]["status"] == "complete"
    assert result["sections"]["design"]["meta"]["status"] == "skipped"


# --- request validation ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"url": "not a url"}, 400),
        ({"url": "ftp://example.test/"}, 400),
        ({"url": "https://127.0.0.1/"}, 403),
        ({"url": "https://localhost/"}, 400),
        ({}, 422),
        ({"url": "https://example.test/", "options": {"unknown": 1}}, 422),
    ],
)
async def test_rejects_bad_requests(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
    payload: dict[str, Any],
    expected_status: int,
) -> None:
    client, _ = api_client
    response = await client.post("/api/v1/scans", json=payload)
    assert response.status_code == expected_status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["status"] == expected_status
    assert problem["code"]
    assert problem["type"].startswith("about:weblens/problem/")


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"url": "https://127.0.0.1/"}, "BLOCKED_TARGET"),
        ({"url": "ftp://example.test/"}, "INVALID_URL"),
        # A schema violation is not a URL problem, and the code must not pretend otherwise.
        ({"url": "https://example.test/", "options": {"unknown": 1}}, "INVALID_REQUEST"),
    ],
)
async def test_error_codes_are_specific(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
    payload: dict[str, Any],
    expected_code: str,
) -> None:
    client, _ = api_client
    response = await client.post("/api/v1/scans", json=payload)
    assert response.json()["code"] == expected_code, response.text


async def test_unknown_scan_returns_problem_document(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    response = await client.get("/api/v1/scans/01ARZ3NDEKTSV4RRFFQ69G5FAV")
    assert response.status_code == 404
    assert response.json()["code"] == "SCAN_NOT_FOUND"


async def test_malformed_scan_id_is_rejected_cheaply(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    assert (await client.get("/api/v1/scans/../../etc/passwd")).status_code in (404, 422)
    assert (await client.get("/api/v1/scans/short")).status_code == 404


async def test_delete_is_idempotent(api_client: tuple[httpx.AsyncClient, FakeCollector]) -> None:
    client, _ = api_client
    assert (await client.delete("/api/v1/scans/01ARZ3NDEKTSV4RRFFQ69G5FAV")).status_code == 204


async def test_ai_endpoint_is_disabled_by_default(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    client, _ = api_client
    scan_id = await submit(client)
    await wait_for_terminal(client, scan_id)
    response = await client.post("/api/v1/ai/explain", json={"scan_id": scan_id})
    assert response.status_code == 501
    assert response.json()["code"] == "AI_DISABLED"


# --- failure isolation (axiom A7) --------------------------------------------------------


class ExplodingAnalyzer:
    id = "seo.structured_data"
    section = SectionKey.SEO
    version = "9.9.9"
    requires = frozenset({EvidenceSlot.DOM})
    depends_on: frozenset[str] = frozenset()

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput:
        raise RuntimeError("simulated analyzer defect")


@pytest.fixture
def registry_with_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Add a deliberately broken analyzer alongside the working one."""
    broken = AnalyzerEntry(
        "seo.structured_data",
        SectionKey.SEO,
        "9.9.9",
        "Deliberately broken analyzer used to prove failure isolation.",
        frozenset({EvidenceSlot.DOM}),
        0,
        factory=ExplodingAnalyzer,
    )
    patched = tuple(
        broken if entry.id == "seo.structured_data" else entry for entry in registry.REGISTRY
    )
    monkeypatch.setattr(registry, "REGISTRY", patched)
    monkeypatch.setattr(registry, "_BY_ID", {entry.id: entry for entry in patched})


async def test_one_analyzer_failing_does_not_destroy_the_scan(
    settings: Settings, registry_with_failure: None, sample_evidence: Any
) -> None:
    """The canonical regression test for partial failure.

    A broken analyzer must degrade its own section and leave everything else intact.
    """
    async with build_client(settings, FakeCollector(sample_evidence)) as (client, _):
        scan_id = await submit(client)
        state = await wait_for_terminal(client, scan_id)
        assert state["status"] == "completed_with_errors"

        result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()
        seo = result["sections"]["seo"]

        # The section survives, degraded, with the working analyzer's findings intact.
        assert seo["meta"]["status"] == "partial"
        assert len(seo["findings"]) >= 11

        runs = {run["id"]: run for run in seo["meta"]["analyzers"]}
        assert runs["seo.metadata"]["status"] == "completed"
        assert runs["seo.structured_data"]["status"] == "failed"
        assert runs["seo.structured_data"]["error_code"] == "ANALYZER_FAILED"
        assert "simulated analyzer defect" in runs["seo.structured_data"]["error_detail"]

        errors = {error["subject"]: error for error in result["errors"]}
        assert errors["seo.structured_data"]["scope"] == "analyzer"


async def test_missing_evidence_skips_an_analyzer_with_a_reason(settings: Settings) -> None:
    """No DOM means the pilot analyzer cannot run, and the section says exactly that."""
    evidence = make_evidence(http=make_http_observation(body=None), dom=None)
    async with build_client(settings, FakeCollector(evidence)) as (client, _):
        scan_id = await submit(client)
        await wait_for_terminal(client, scan_id)
        result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()

        seo = result["sections"]["seo"]
        assert seo["meta"]["status"] == "unavailable"
        run = next(r for r in seo["meta"]["analyzers"] if r["id"] == "seo.metadata")
        assert run["status"] == "skipped"
        assert run["error_code"] == "MISSING_EVIDENCE"
        assert run["missing_evidence"] == ["dom"]


async def test_collection_failure_fails_the_scan_with_a_problem(
    settings: Settings, sample_evidence: Any
) -> None:
    """Unreachable target: a scan-level failure, reported as a problem on the job."""
    collector = FakeCollector(sample_evidence, error=ConnectFailureError("host unreachable"))
    async with build_client(settings, collector) as (client, _):
        scan_id = await submit(client)
        state = await wait_for_terminal(client, scan_id)
        assert state["status"] == "failed"
        assert state["problem"]["code"] == "CONNECT_FAILURE"
        assert state["problem"]["retryable"] is True

        # No result exists, and the API says why rather than returning an empty report.
        response = await client.get(f"/api/v1/scans/{scan_id}/result")
        assert response.status_code == 410


async def test_result_is_409_while_running(settings: Settings, sample_evidence: Any) -> None:
    class SlowCollector(FakeCollector):
        async def collect(self, target: Any, options: Any, sink: Any) -> Any:
            await asyncio.sleep(0.3)
            return await super().collect(target, options, sink)

    async with build_client(settings, SlowCollector(sample_evidence)) as (client, _):
        scan_id = await submit(client)
        response = await client.get(f"/api/v1/scans/{scan_id}/result")
        assert response.status_code == 409
        assert response.json()["code"] == "SCAN_IN_PROGRESS"
        await wait_for_terminal(client, scan_id)


async def test_per_host_concurrency_is_limited(settings: Settings, sample_evidence: Any) -> None:
    class SlowCollector(FakeCollector):
        async def collect(self, target: Any, options: Any, sink: Any) -> Any:
            await asyncio.sleep(0.5)
            return await super().collect(target, options, sink)

    polite = settings.model_copy(update={"max_concurrent_scans_per_host": 1})
    async with build_client(polite, SlowCollector(sample_evidence)) as (client, _):
        first = await client.post("/api/v1/scans", json={"url": "https://example.test/"})
        assert first.status_code == 202
        second = await client.post("/api/v1/scans", json={"url": "https://example.test/"})
        assert second.status_code == 429
        assert second.json()["code"] == "RATE_LIMITED"
        assert "Retry-After" in second.headers
        await wait_for_terminal(client, first.json()["scan_id"])


async def test_every_declared_stage_has_a_recorded_outcome(
    api_client: tuple[httpx.AsyncClient, FakeCollector],
) -> None:
    """No stage may be left as 'pending' or 'running' in a stored result.

    A result is read long after the scan, so a stage frozen mid-flight would be a permanent
    misstatement about what happened.
    """
    client, _ = api_client
    scan_id = await submit(client)
    await wait_for_terminal(client, scan_id)
    result = (await client.get(f"/api/v1/scans/{scan_id}/result")).json()

    stages = {stage["key"]: stage for stage in result["scan"]["stages"]}
    assert stages, "the result must record stage outcomes"
    for key, stage in stages.items():
        assert stage["status"] in ("completed", "failed", "skipped"), f"{key} is {stage['status']}"
        if stage["status"] == "skipped":
            assert stage["skip_reason"], f"{key} was skipped without a reason"

    assert stages["assemble"]["status"] == "completed"
    assert stages["a11y_capture"]["status"] == "skipped"
