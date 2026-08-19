# WebLens

Website Technical Intelligence Analyzer. Give it a public URL; it collects observable evidence from
the site with a real browser plus HTTP/TLS probes, runs deterministic analyzers over that evidence,
and produces a technical report across design, technology, security, performance, accessibility, SEO,
architecture, and network.

**Detection is not done by AI.** Every asserted fact is derived from collected evidence and carries
the provenance for that evidence. When something cannot be determined, WebLens says so instead of
guessing. The optional AI layer only explains findings that already exist, and any statement it
produces that cannot be traced to a finding is dropped.

## Status

Phase 0 — blueprint and skeleton. The architecture, contracts, and plumbing are in place and running
end to end through one pilot analyzer (`seo.metadata`). The remaining analyzers are registered and
report `not_implemented`, which the UI and reports render honestly. See
[docs/blueprint/13-development-phases.md](docs/blueprint/13-development-phases.md).

## Requirements

- Python 3.12 (Playwright does not yet support 3.14; `pyproject.toml` enforces `>=3.12,<3.13`)
- Node.js 20+
- ~150 MB of disk for the Chromium build Playwright downloads

## Setup

```bash
make setup            # backend venv + deps + Chromium; frontend npm install
```

`make setup` runs `playwright install chromium`, which downloads a browser build from Microsoft's CDN.
It is the only setup step that fetches a large artifact.

## Run

```bash
make dev-backend      # http://127.0.0.1:8000  (docs at /docs)
make dev-frontend     # http://127.0.0.1:5173
```

Both bind to loopback by default.

## Checks

```bash
make check            # ruff + mypy + pytest (offline) + tsc + eslint + vitest
make test-live        # opt-in, hits the network (WEBLENS_LIVE=1)
make contracts        # regenerate contracts/openapi.json + frontend types
```

## How it works

```
URL → validate + guard → collect (HTTP, TLS, DNS, robots, Playwright) → RawEvidence
    → deterministic analyzers → AnalysisResult → API → IndexedDB → dashboard + downloadable reports
```

Scan results are stored in the **browser** (IndexedDB) and survive refresh and browser restart. The
backend holds a result only until the client confirms it has persisted it, then drops it — there is no
database in V1, and the backend is not a data store. Deleting a scan in the UI removes it from
IndexedDB permanently; there is no server copy to restore from.

Reports (`design.md`, `techstack.md`, `security.md`, `performance.md`, `accessibility.md`, `seo.md`,
`architecture.md`, `analysis.json`, `complete-report.zip`) are generated client-side from the stored
result, so exports keep working with the backend stopped.

## What WebLens does not do

- No offensive security testing. Analysis is passive: it observes what a normal visit reveals. No
  exploitation, credential attacks, authentication bypass, brute force, fuzzing, or destructive tests.
- No crawling. One URL per scan.
- No authenticated, paywalled, or geo-restricted content.
- No bypassing bot protection or consent walls. When a challenge page is detected, WebLens reports
  restricted access rather than describing the interstitial as if it were the site.
- No scores except the security posture score, which exists because it communicates observable
  configuration against [documented rules](docs/blueprint/11-security-scoring-methodology.md). It is
  not a vulnerability assessment and cannot establish that a site is secure or insecure.

Full list: [docs/limitations.md](docs/limitations.md).

## Security note for operators

V1 has no authentication, by design, and the API fetches URLs you give it. That makes it a
request-forwarding surface. It ships with loopback binding, a CORS allowlist, scheme/port
restrictions, and DNS-resolution guards that reject loopback, private, link-local, CGNAT, reserved,
and cloud-metadata addresses — re-checked on every redirect hop.

**Do not expose this service to an untrusted network without adding authentication and egress
controls.** It is a local developer tool.

## Documentation

- [Blueprint index](docs/blueprint/00-index.md) — architecture, contracts, models, methodology
- [Decisions](docs/blueprint/decisions.md) — what we chose, what we rejected, and why
- [Limitations](docs/limitations.md) — what the tool structurally cannot tell you

## Layout

```
backend/    FastAPI + Playwright collection + deterministic analyzers
frontend/   React + Vite + Tailwind + shadcn/ui dashboard, IndexedDB persistence, report generation
contracts/  generated OpenAPI schema shared by both sides
docs/       blueprint and limitations
```

## Third-party notices

The accessibility stage uses [axe-core](https://github.com/dequelabs/axe-core) (Mozilla Public
License 2.0), vendored and pinned under `backend/src/weblens/vendor/axe/` with its license, so
accessibility results are reproducible and no per-scan CDN fetch is required.
