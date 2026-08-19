# 1. Repository structure

Single repository, two deployable apps, one shared contract directory. No monorepo tooling (no
Nx/Turbo/workspaces) — two independent toolchains talking over HTTP is simpler and matches the
stack constraints.

```
weblens/
├── README.md                     # what it is, how to run, what it does not do
├── Makefile                      # setup / dev / test / lint / contracts entrypoints
├── .editorconfig
├── .gitignore
│
├── docs/
│   ├── blueprint/                # this blueprint (design source of truth)
│   └── limitations.md            # user-facing catalogue of known limits (referenced by reports)
│
├── contracts/
│   ├── openapi.json              # exported from FastAPI, committed, drift-checked in CI
│   └── README.md                 # how to regenerate
│
├── backend/
│   ├── pyproject.toml            # deps + ruff + mypy + pytest config
│   ├── .env.example
│   ├── src/weblens/
│   │   ├── main.py               # app factory + lifespan
│   │   ├── config.py             # pydantic-settings, single source of tunables
│   │   ├── logging.py            # centralized structured logging
│   │   ├── version.py            # ENGINE_VERSION, SCHEMA_VERSION
│   │   │
│   │   ├── api/                  # transport layer only: no analysis logic
│   │   │   ├── router.py
│   │   │   ├── problems.py       # RFC 9457 problem+json mapping
│   │   │   ├── deps.py
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── capabilities.py
│   │   │       ├── scans.py
│   │   │       └── ai.py
│   │   │
│   │   ├── domain/               # pure types. no I/O, no imports from api/collection
│   │   │   ├── enums.py
│   │   │   ├── evidence.py       # RawEvidence + EvidenceRef
│   │   │   ├── observations/     # the observation models RawEvidence is composed of
│   │   │   │   ├── transport.py  # target, HTTP, DNS, robots, TLS
│   │   │   │   ├── page.py       # DOM, runtime, styles, viewports, screenshots
│   │   │   │   └── measurement.py# network ledger, performance, axe
│   │   │   ├── findings.py       # Finding, Interpretation
│   │   │   ├── sections.py       # per-section payloads + SectionSet
│   │   │   ├── security.py       # SecurityScore, SecurityRuleResult
│   │   │   ├── scan.py           # ScanRequest, ScanJobState, AnalysisResult
│   │   │   └── errors.py         # ScanError, ErrorCode, WebLensError hierarchy
│   │   │
│   │   ├── collection/           # everything that touches the network
│   │   │   ├── base.py           # Collector protocol + StageSink seam
│   │   │   ├── target.py         # normalization + SSRF/private-range guard
│   │   │   ├── http_probe.py     # redirect chain, headers, cookies, raw HTML
│   │   │   ├── http_collector.py # HTTP-only collector (Phase 0, and the browserless fallback)
│   │   │   ├── static_html.py    # DOM inventory from served HTML
│   │   │   ├── robots.py         # robots.txt fetch + path permission check
│   │   │   ├── browser.py        # Playwright availability; lifecycle from Phase 1
│   │   │   ├── tls_probe.py      # protocol/cipher/cert metadata (Phase 2)
│   │   │   ├── page_collector.py # navigation + in-page capture (Phase 1)
│   │   │   ├── recorders/        # per-concern capture (network, console, perf)
│   │   │   └── probes/*.js       # injected read-only capture scripts
│   │   │
│   │   ├── orchestration/
│   │   │   ├── pipeline.py       # stage sequencing, per-analyzer isolation
│   │   │   ├── service.py        # admission control, scheduling, failure translation
│   │   │   ├── stages.py         # stage definitions + weights for progress
│   │   │   ├── registry.py       # analyzer registration + capability report
│   │   │   ├── progress.py       # observable progress channel (SSE source)
│   │   │   └── job_store.py      # ephemeral in-memory jobs with TTL eviction
│   │   │
│   │   ├── analyzers/            # deterministic, pure, unit-testable
│   │   │   ├── base.py           # Analyzer protocol + AnalyzerContext + helpers
│   │   │   ├── technology/       # signature engine + data files
│   │   │   ├── design/
│   │   │   ├── security/         # headers, cookies, tls, mixed content, scoring
│   │   │   ├── performance/
│   │   │   ├── accessibility/
│   │   │   ├── seo/
│   │   │   ├── network/
│   │   │   └── architecture/
│   │   │
│   │   ├── ai/                   # optional presentation layer, disabled by default
│   │   │   ├── provider.py       # Protocol + NullProvider
│   │   │   ├── grounding.py      # drops claims without a finding reference
│   │   │   └── prompts/
│   │   └── utils/                # urls, color, bytes, timing, text truncation
│   │
│   ├── tests/
│   │   ├── unit/                 # analyzers over recorded fixtures
│   │   ├── api/                  # ASGI-level, collection layer faked
│   │   ├── live/                 # opt-in, network-dependent (WEBLENS_LIVE=1)
│   │   └── fixtures/evidence/    # committed RawEvidence snapshots
│   └── scripts/
│       ├── export_openapi.py
│       └── capture_evidence.py   # records a fixture from a real site
│
└── frontend/
    ├── package.json
    ├── vite.config.ts            # dev server + build; proxies /api and /health to the backend
    ├── vitest.config.ts          # separate so the test environment cannot silently stop applying
    ├── eslint.config.js
    ├── components.json           # shadcn/ui config
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── routes/               # route components only
        ├── components/
        │   ├── ui/               # shadcn/ui primitives (generated, unmodified)
        │   ├── layout/
        │   ├── scan/             # url form, progress, stage list
        │   └── sections/         # one component per report section
        ├── features/
        │   ├── scan/             # api hooks + scan lifecycle
        │   ├── history/          # local scan library
        │   └── reports/          # markdown/json/zip generation
        ├── lib/
        │   ├── api/              # typed client, zod parsing, problem handling
        │   ├── db/               # IndexedDB schema, migrations, repository
        │   ├── prefs/            # localStorage (theme + UI prefs only)
        │   └── format/           # bytes, ms, colors, urls
        ├── types/
        │   ├── api.generated.ts  # from contracts/openapi.json
        │   └── analysis.ts       # hand-authored domain types + zod schemas
        └── test/                 # setup, factories, fixtures
```

## Structural rules

1. **Import direction is one-way:** `api → orchestration → {collection, analyzers} → domain → utils`.
   `domain` imports nothing from the layers above it; `analyzers` never import `collection`.
   (Analyzers receive already-collected evidence, so they cannot make requests even accidentally.)
2. **No file over ~400 lines of logic.** A grown analyzer splits into `analyzer.py` plus
   rule/signature modules. Declarative data (the security rule table, analyzer registry, signature
   sets, schema definitions) and generated files (`api.generated.ts`) are exempt — the rule exists to
   stop tangled control flow, not to cap tables that are read top to bottom.
3. **No magic constants.** Thresholds live in `config.py`, scoring weights in
   `analyzers/security/rules.py`, signatures in data files under `analyzers/technology/signatures/`.
4. **Frontend mirrors sections.** Adding a section means one component in `components/sections/`
   and one renderer in `features/reports/renderers/` — nothing else.
5. **`contracts/openapi.json` is generated, never hand-edited.** `make contracts` regenerates it and
   the TypeScript types derived from it.
