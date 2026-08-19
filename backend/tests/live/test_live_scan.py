"""Live scanner tests. Opt-in: ``WEBLENS_LIVE=1 make test-live``.

Assertions here are deliberately **structural**, never value-based. Whether example.com has a
meta description is not ours to control, and asserting it would make this suite a liability that
fails for reasons unrelated to our code. What we assert is that the scan completes, the stages
ran, findings carry provenance, and the request pattern stays polite.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from weblens.config import Settings
from weblens.main import create_app

pytestmark = pytest.mark.live

TARGET = "https://example.com/"
TERMINAL = {"completed", "completed_with_errors", "failed"}


@pytest.fixture
def live_settings(live_enabled: bool) -> Settings:
    if not live_enabled:
        pytest.skip("set WEBLENS_LIVE=1 to run network tests")
    return Settings(min_host_interval_seconds=0.0, log_level="WARNING")


async def _scan(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.post("/api/v1/scans", json={"url": url})
    assert response.status_code == 202, response.text
    scan_id = response.json()["scan_id"]
    for _ in range(300):
        state = (await client.get(f"/api/v1/scans/{scan_id}")).json()
        if state["status"] in TERMINAL:
            break
        await asyncio.sleep(0.1)
    else:
        raise AssertionError("live scan did not finish")
    assert state["status"] != "failed", state.get("problem")
    return dict((await client.get(f"/api/v1/scans/{scan_id}/result")).json())


async def test_live_scan_produces_a_structurally_valid_result(live_settings: Settings) -> None:
    app = create_app(settings=live_settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://weblens.test", timeout=60
        ) as client:
            result = await _scan(client, TARGET)

    assert result["schema_version"] == "1.0"
    assert result["target"]["final_url"]
    assert result["target"]["http_status"] == 200
    assert result["scan"]["run_context"]["collection_mode"] == "http_only"

    stages = {stage["key"]: stage for stage in result["scan"]["stages"]}
    assert stages["http_probe"]["status"] == "completed"
    assert stages["analyze"]["status"] == "completed"
    # Stages this build does not implement must be visibly skipped, not silently absent.
    assert stages["a11y_capture"]["status"] == "skipped"
    assert stages["a11y_capture"]["skip_reason"]

    seo = result["sections"]["seo"]
    assert seo["meta"]["status"] in ("complete", "partial")
    assert seo["findings"]

    for finding in seo["findings"]:
        if finding["status"] in ("verified", "inferred"):
            assert finding["evidence"], f"{finding['id']} asserted without evidence"
        else:
            assert finding["reason"], f"{finding['id']} negative without a reason"


async def test_live_scan_request_pattern_stays_polite(live_settings: Settings) -> None:
    """One scan must not turn into a crawl.

    Expected requests for an HTTP-only scan: robots.txt, the document, and the optional
    single HEAD probe of the http:// origin.
    """
    from weblens.collection import http_probe

    requests: list[tuple[str, str]] = []
    original = http_probe.HttpProbe._request

    async def counting_request(self, client, method, url):  # type: ignore[no-untyped-def]
        requests.append((method, url))
        return await original(self, client, method, url)

    http_probe.HttpProbe._request = counting_request  # type: ignore[method-assign]
    try:
        app = create_app(settings=live_settings)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://weblens.test", timeout=60
            ) as client:
                await _scan(client, TARGET)
    finally:
        http_probe.HttpProbe._request = original  # type: ignore[method-assign]

    assert len(requests) <= 4, requests
    assert sum(1 for method, _ in requests if method == "GET") <= 3
