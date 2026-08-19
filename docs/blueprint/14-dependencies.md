# 14. Dependency list

Every dependency is pinned to an exact version. Versions below are the ones resolved at scaffolding
time (2026-08-19) and recorded in `backend/pyproject.toml` and `frontend/package.json`.

Selection rules applied: prefer the standard library / platform API; add a dependency only when it
removes real complexity; avoid anything unmaintained or narrowly-owned; no transitive-heavy utility
kitchen sinks.

## Backend runtime (Python 3.12)

| Package | Version | Why | Alternative rejected |
|---------|---------|-----|----------------------|
| `fastapi` | 0.141.1 | required by spec; Pydantic-native, generates the OpenAPI we build contracts from | — |
| `uvicorn[standard]` | 0.52.4 | ASGI server; `standard` brings `httptools`/`uvloop` for real throughput | — |
| `pydantic` | 2.13.4 | the domain model layer; validators enforce provenance invariants | dataclasses (no validation, no JSON schema) |
| `pydantic-settings` | 2.15.0 | typed config from env, one source of tunables | manual `os.environ` reads |
| `httpx` | 0.28.1 | async HTTP for probes; explicit redirect control, HTTP/2 | `requests` (sync only), `aiohttp` (heavier API) |
| `playwright` | 1.62.0 | required by spec; the only way to get real runtime/perf/style evidence | static fetching (cannot see rendered DOM) |

**Python version:** 3.12. The machine's default is 3.14, which Playwright does not yet advertise
support for; 3.12 is the newest version with wheels for the whole stack. Pinned via
`requires-python = ">=3.12,<3.13"` so the mismatch fails at install time, not at runtime.

Deliberately absent: no ORM, no database driver, no Redis client, no Celery, no `requests`, no
BeautifulSoup (DOM inventory comes from the browser, and `html.parser` covers static-HTML fallback),
no `python-whois`/`dnspython` in V1 (DNS observations use `asyncio.getaddrinfo`; a resolver library
arrives only if CNAME chain evidence proves necessary).

`ulid` is not a dependency — ULID generation is ~15 lines over `os.urandom` + `time.time_ns` and lives
in `utils/ids.py`. A supply-chain surface for that is not worth it.

## Backend vendored

| Asset | Version | Why vendored |
|-------|---------|--------------|
| `axe-core` (`vendor/axe/axe.min.js`) | pinned, MPL-2.0, license file included | the accessibility rule engine must be byte-stable for reproducible results; fetching it at scan time would make results depend on a CDN and add a network call per scan |

## Backend dev

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | 9.1.1 | test runner |
| `pytest-asyncio` | 1.4.0 | async pipeline/API tests |
| `respx` | 0.23.1 | httpx mocking for probe tests without sockets |
| `ruff` | 0.16.3 | lint + format, replaces black/isort/flake8 |
| `mypy` | 2.3.1 | strict typing on `domain/` and `analyzers/` |
| `import-linter` | latest at setup | enforces the layer boundaries from doc 3 in CI |

## Frontend runtime

| Package | Version | Why | Alternative rejected |
|---------|---------|-----|----------------------|
| `react` / `react-dom` | 19.2.8 | required by spec | — |
| `react-router-dom` | 7.18.2 | deep-linkable scans/sections | hash routing (worse UX, no nested routes) |
| `@tanstack/react-query` | 5.101.4 | job polling/SSE-backed async state, cache over IndexedDB reads | hand-rolled effects (retry/cancel/dedupe bugs) |
| `zod` | 4.4.3 | runtime validation at the API and IndexedDB boundaries | trusting types (no runtime guarantee) |
| `idb` | 8.0.3 | thin promise wrapper over IndexedDB | raw IDB (verbose, error-prone), Dexie (query DSL we do not need) |
| `fflate` | 0.8.3 | client-side zip for `complete-report.zip`, small and fast | JSZip (larger, slower) |
| `lucide-react` | 1.32.0 | icon set used by shadcn/ui | icon fonts |
| `class-variance-authority` | 0.7.1 | shadcn/ui variant contract | ad-hoc class strings |
| `clsx` | 2.1.1 | conditional classes | string concatenation |
| `tailwind-merge` | 3.6.0 | conflict-free class merging in `cn()` | manual ordering discipline |
| `@radix-ui/*` primitives | as pulled by shadcn components | accessible unstyled primitives (dialog, tabs, tooltip, popover, dropdown) | custom-built widgets (accessibility risk) |

## Frontend build/dev

| Package | Version | Purpose |
|---------|---------|---------|
| `vite` | 8.2.1 | required by spec; dev server + build |
| `@vitejs/plugin-react` | 6.0.5 | React transform + HMR |
| `typescript` | 5.9.3 | type checking — see the note below on why not 7.x |
| `@eslint/js` | pinned at setup | base rule set the flat config extends |
| `tailwindcss` + `@tailwindcss/vite` | 4.3.3 | required by spec; v4 CSS-first config, no `tailwind.config.js` |
| `tw-animate-css` | 1.4.0 | animation utilities shadcn/ui expects under Tailwind v4 |
| `vitest` | 4.1.11 | unit/component tests, shares the Vite pipeline |
| `@testing-library/react` + `/jest-dom` + `/user-event` | latest at setup | component tests from the user's perspective |
| `fake-indexeddb` | 6.2.5 | real IndexedDB semantics in Node for persistence tests |
| `jsdom` | latest at setup | DOM for component tests |
| `openapi-typescript` | 7.13.0 | generates `api.generated.ts` from `contracts/openapi.json` |
| `eslint` + `typescript-eslint` + react plugins | latest at setup | lint |
| `@axe-core/react` or `axe-core` (dev only) | pinned at setup | accessibility assertions for WebLens' own UI |

shadcn/ui is **not** a dependency — it is a generator. Components are copied into
`src/components/ui/` and versioned with the app, which is the point of the model: no upstream breakage,
full control, `components.json` records the configuration used.

## Version choices that fought the ecosystem

**TypeScript 5.9.3, not 7.0.2.** TypeScript 7 is `latest` on npm, but `openapi-typescript@7.13.0`
declares a `typescript@^5.x` peer, and typescript-eslint has not published support either. Installing
7.x requires `--force` or `--legacy-peer-deps`, which is how a project ends up with a dependency tree
nobody can reason about. 5.9.3 is the newest version the whole toolchain actually supports; revisit
when `openapi-typescript` and typescript-eslint ship 7.x support.

**jsdom 30 no longer provides Web Storage,** and recent Node versions expose a global `localStorage`
that is unusable without `--localstorage-file`. Rather than mocking the preferences module — which
would stop testing the real read/write path — the test setup installs a small real `Storage`
implementation (`src/test/localStorage.ts`) and the app always reaches storage through
`window.localStorage`, never the bare global.

## Explicitly excluded (per requirements and judgement)

PostgreSQL, Supabase, Firebase, Redis, Docker, any auth provider, any cloud SDK, any analytics or
telemetry in either app, Lighthouse (its scoring model conflicts with axiom A4 and it would duplicate
the browser session), Wappalyzer's dataset (licence + we need evidence-linked detection, not a
verdict), any LLM SDK in the default install path (the AI layer's provider is an optional extra:
`pip install weblens[ai]`).

## Install surface

```
make setup           # backend venv (python3.12) + pip install -e .[dev] + playwright install chromium
                     # frontend npm ci
make dev-backend     # uvicorn --reload on 127.0.0.1:8000
make dev-frontend    # vite dev server on 127.0.0.1:5173
make check           # ruff + mypy + pytest (not live) + tsc + eslint + vitest
make contracts       # export openapi.json + regenerate api.generated.ts
```

`playwright install chromium` downloads a browser build (~150 MB) into the user's Playwright cache.
That is the one setup step that reaches the network for a large artifact, and it is called out in the
README rather than hidden inside another target.
