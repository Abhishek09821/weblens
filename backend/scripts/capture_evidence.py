#!/usr/bin/env python
"""Capture a real collection run as a committed test fixture.

This is the hinge of the testing strategy (docs/blueprint/12): ``RawEvidence`` is serializable,
so one real run against a site becomes a deterministic, offline fixture that every analyzer test
can rely on forever. Analyzer changes are then validated against real-world shapes without
touching the network.

    python backend/scripts/capture_evidence.py https://example.com --name static_html_minimal

Fixtures are regenerated deliberately, never automatically by a test run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "evidence"


class _NullSink:
    """Stage sink that prints transitions instead of publishing them."""

    async def stage_started(self, key: object) -> None:
        print(f"  → {key}")

    async def stage_completed(self, key: object) -> None:
        pass

    async def stage_failed(self, key: object, code: object, detail: str) -> None:
        print(f"  ! {key} failed: {code} {detail}")

    async def stage_skipped(self, key: object, reason: str) -> None:
        print(f"  - {key} skipped: {reason}")


async def capture(url: str) -> dict[str, object]:
    from weblens.collection.http_collector import HttpEvidenceCollector
    from weblens.collection.target import TargetGuard
    from weblens.config import get_settings
    from weblens.domain.scan import ScanOptions

    settings = get_settings()
    guard = TargetGuard(settings)
    collector = HttpEvidenceCollector(settings, guard)

    print(f"capturing {url}")
    target = await guard.prepare(url)
    outcome = await collector.collect(target, ScanOptions(), _NullSink())  # type: ignore[arg-type]

    return {
        "captured_from": target.display_url,
        "collection_mode": collector.collection_mode,
        "evidence": outcome.evidence.model_dump(mode="json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--name", required=True, help="Fixture file name without extension.")
    parser.add_argument("--out", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()

    payload = asyncio.run(capture(args.url))

    args.out.mkdir(parents=True, exist_ok=True)
    destination: Path = args.out / f"{args.name}.json"
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {destination}")
    print(
        "Review the file before committing: it contains content from a third-party site, and "
        "fixtures are part of the test suite's contract."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
