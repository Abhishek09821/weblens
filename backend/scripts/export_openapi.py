#!/usr/bin/env python
"""Export the OpenAPI schema to ``contracts/openapi.json``.

Builds the app without starting a server. Keys are sorted and a trailing newline is written so
the file is a stable, reviewable diff - CI regenerates it and fails if the working tree changes,
which turns contract drift into a build error instead of a runtime surprise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "contracts" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the file on disk differs from the generated schema.",
    )
    args = parser.parse_args()

    from weblens.main import create_app

    schema = create_app().openapi()
    rendered = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if args.check:
        if not args.out.exists():
            print(f"{args.out} does not exist. Run: make contracts", file=sys.stderr)
            return 1
        if args.out.read_text(encoding="utf-8") != rendered:
            print(f"{args.out} is out of date. Run: make contracts", file=sys.stderr)
            return 1
        print(f"{args.out} is up to date.")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.out} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
