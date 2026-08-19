"""Real smoke test: scan a public website end-to-end and validate the result.

This script starts the WebLens API server, submits a scan of a real public website,
waits for it to complete, and validates that the structured result contains actual
collected evidence across all sections.

Usage:
    python scripts/smoke_test.py [url]
    Default URL: https://example.com
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx

TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 90  # seconds


async def main() -> int:
    print(f"=== WebLens Smoke Test ===")
    print(f"Target: {TARGET_URL}")
    print()

    # Start the server in background
    import uvicorn
    from weblens.main import create_app
    from weblens.config import Settings

    settings = Settings(
        log_level="WARNING",
        allow_private_targets=False,
    )
    app = create_app(settings=settings)

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    # Run server in background
    server_task = asyncio.create_task(server.serve())
    await asyncio.sleep(1.0)  # Give server time to start

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            # Check health
            health = await client.get("/health")
            assert health.status_code == 200, f"Health check failed: {health.status_code}"
            print(f"[OK] Server healthy: {health.json()['engine_version']}")

            # Submit scan
            print(f"\n[..] Submitting scan for {TARGET_URL}...")
            response = await client.post("/api/v1/scans", json={"url": TARGET_URL})
            assert response.status_code == 202, f"Submit failed: {response.status_code} - {response.text}"
            scan_data = response.json()
            scan_id = scan_data["scan_id"]
            print(f"[OK] Scan accepted: {scan_id}")

            # Poll for completion
            start = time.monotonic()
            while time.monotonic() - start < TIMEOUT:
                state = await client.get(f"/api/v1/scans/{scan_id}")
                status = state.json()["status"]
                if status in ("completed", "completed_with_errors", "failed"):
                    break
                await asyncio.sleep(1.0)
            else:
                print(f"[FAIL] Scan timed out after {TIMEOUT}s")
                return 1

            elapsed = time.monotonic() - start
            print(f"[OK] Scan finished in {elapsed:.1f}s with status: {status}")

            if status == "failed":
                print(f"[FAIL] Scan failed: {state.json().get('problem')}")
                return 1

            # Get result
            result_resp = await client.get(f"/api/v1/scans/{scan_id}/result")
            assert result_resp.status_code == 200, f"Result fetch failed: {result_resp.status_code}"
            result = result_resp.json()

            # Validate structure
            print(f"\n=== Result Validation ===")
            print(f"Schema version: {result['schema_version']}")
            print(f"Scan status: {result['scan']['status']}")
            print(f"Duration: {result['scan']['duration_ms']:.0f}ms")
            print(f"Collection mode: {result['scan']['run_context']['collection_mode']}")
            print(f"Target host: {result['target']['host']}")
            print(f"Final URL: {result['target']['final_url']}")
            print(f"Errors: {len(result['errors'])}")
            print(f"Limitations: {len(result['limitations'])}")

            # Validate sections
            print(f"\n=== Sections ===")
            total_findings = 0
            for section_key in ("seo", "security", "technology", "design",
                                "performance", "accessibility", "architecture", "network"):
                section = result["sections"][section_key]
                section_status = section["meta"]["status"]
                findings_count = len(section["findings"])
                total_findings += findings_count
                has_data = section["data"] is not None
                analyzers = section["meta"]["analyzers"]
                completed = sum(1 for a in analyzers if a["status"] == "completed")
                print(f"  {section_key:15s} | status={section_status:12s} | "
                      f"findings={findings_count:3d} | analyzers={completed}/{len(analyzers)} | "
                      f"data={'yes' if has_data else 'no'}")

            print(f"\n  Total findings: {total_findings}")

            # Validate key evidence was collected
            print(f"\n=== Evidence Validation ===")
            errors = []

            # SEO should always have findings
            seo = result["sections"]["seo"]
            if not seo["findings"]:
                errors.append("SEO section has no findings")
            else:
                print(f"[OK] SEO: {len(seo['findings'])} findings")
                # Check specific metadata was collected
                titles = [f for f in seo["findings"] if "title" in f["name"].lower()
                          and f["status"] == "verified"]
                if titles:
                    print(f"     Title: {titles[0].get('value', 'N/A')}")

            # Security should have header findings
            sec = result["sections"]["security"]
            if not sec["findings"]:
                errors.append("Security section has no findings")
            else:
                print(f"[OK] Security: {len(sec['findings'])} findings")
                https_f = [f for f in sec["findings"] if f["id"] == "security.headers:https"]
                if https_f:
                    print(f"     HTTPS: {https_f[0].get('value')}")
                # Check for security score
                if sec["data"] and sec["data"].get("score"):
                    score = sec["data"]["score"]
                    print(f"     Security Score: {score['percentage']}% ({score['band']})")

            # Technology
            tech = result["sections"]["technology"]
            if tech["findings"]:
                print(f"[OK] Technology: {len(tech['findings'])} findings")
                detected = [f for f in tech["findings"] if f["status"] == "verified"]
                for f in detected[:5]:
                    print(f"     - {f['name']}: {f.get('value', '')}")
            else:
                print(f"[--] Technology: no findings (expected for simple sites)")

            # Performance
            perf = result["sections"]["performance"]
            if perf["findings"]:
                print(f"[OK] Performance: {len(perf['findings'])} findings")
                for f in perf["findings"][:3]:
                    if f.get("unit") == "ms":
                        print(f"     {f['name']}: {f.get('value')}ms")
            else:
                print(f"[--] Performance: no findings (browser collection may not have run)")

            # Accessibility
            a11y = result["sections"]["accessibility"]
            if a11y["findings"]:
                print(f"[OK] Accessibility: {len(a11y['findings'])} findings")
            else:
                print(f"[--] Accessibility: no findings")

            # Network
            net = result["sections"]["network"]
            if net["findings"]:
                print(f"[OK] Network: {len(net['findings'])} findings")
            else:
                print(f"[--] Network: no findings (needs browser collection)")

            # Architecture
            arch = result["sections"]["architecture"]
            if arch["findings"]:
                print(f"[OK] Architecture: {len(arch['findings'])} findings")
            else:
                print(f"[--] Architecture: no findings")

            # Design
            design = result["sections"]["design"]
            if design["findings"]:
                print(f"[OK] Design: {len(design['findings'])} findings")
            else:
                print(f"[--] Design: no findings (needs browser style collection)")

            # Evidence provenance check
            print(f"\n=== Provenance Check ===")
            verified_findings = [
                f for sec_key in result["sections"]
                for f in result["sections"][sec_key]["findings"]
                if f["status"] in ("verified", "inferred")
            ]
            without_evidence = [f for f in verified_findings if not f.get("evidence")]
            print(f"Verified/inferred findings: {len(verified_findings)}")
            print(f"Without evidence (BUG if >0): {len(without_evidence)}")
            if without_evidence:
                for f in without_evidence[:5]:
                    errors.append(f"Finding {f['id']} is {f['status']} without evidence")

            # Summary
            print(f"\n=== Summary ===")
            if errors:
                print(f"ERRORS ({len(errors)}):")
                for e in errors:
                    print(f"  - {e}")
                return 1
            else:
                print(f"SMOKE TEST PASSED")
                print(f"  - {total_findings} findings across all sections")
                print(f"  - All verified findings carry evidence")
                print(f"  - Scan completed in {elapsed:.1f}s")
                return 0

    finally:
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
