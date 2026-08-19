# 3. Backend architecture

FastAPI + Pydantic v2 + Playwright, single process, async, no external services.

## Layer responsibilities

| Layer | Owns | Forbidden |
|-------|------|-----------|
| `api/` | HTTP shape, status codes, problem+json, SSE framing | analysis logic, Playwright calls |
| `orchestration/` | stage sequencing, progress, job lifecycle, analyzer isolation | knowing how any single analyzer works |
| `collection/` | all network I/O, browser lifecycle, evidence capture | interpreting what evidence means |
| `analyzers/` | deterministic evidence → findings | any I/O, any hostname special-casing |
| `domain/` | types, enums, invariants | imports from any layer above |
| `ai/` | optional narrative over finished findings | producing findings, being on the scan path |

The hard boundary is `collection/` ↔ `analyzers/`: `RawEvidence` is the only thing that crosses it.
Analyzers are pure functions, which is what makes them unit-testable from committed fixtures and
what structurally prevents "analyzer quietly makes another request" bugs.

## Request lifecycle

```
POST /api/v1/scans
  ├─ validate ScanRequest (pydantic)
  ├─ normalize + guard target  ── reject → 400/403 problem
  ├─ rate/concurrency admission ── reject → 429 problem
  ├─ create Job(id, QUEUED) in job_store
  ├─ schedule pipeline task on the running loop
  └─ 202 { scan_id, status, links }

GET  /api/v1/scans/{id}          → ScanJobState (status + stage progress)
GET  /api/v1/scans/{id}/events   → SSE: stage / status / done / error
GET  /api/v1/scans/{id}/result   → AnalysisResult (410 once evicted)
DELETE /api/v1/scans/{id}        → 204, evict immediately
```

## Job store (explicitly ephemeral)

`orchestration/job_store.py`: `dict[str, Job]` behind an `asyncio.Lock`, with

- TTL eviction (`settings.result_ttl_seconds`, default 900) via a lazy sweep on each access plus a
  periodic task started in the app lifespan,
- a hard cap on retained results (`settings.max_retained_results`, LRU eviction),
- `DELETE` for immediate removal once the client has persisted the result.

Consequences documented rather than engineered around in V1: results are lost on restart, and the
process is not horizontally scalable. Both are acceptable because the browser owns persistence.
The store is defined behind a small `JobStore` protocol so a future durable implementation is a
drop-in.

## Concurrency and politeness

Browser work is the scarce resource. Controls, all in `config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_concurrent_scans` | 2 | global semaphore around the pipeline |
| `max_concurrent_scans_per_host` | 1 | never hammer one target |
| `min_host_interval_seconds` | 5 | spacing between scans of the same host |
| `navigation_timeout_ms` | 30000 | per-navigation cap |
| `total_scan_budget_ms` | 90000 | whole-pipeline deadline; stages past the budget are skipped, not truncated silently |
| `max_resource_bytes_captured` | 2 MiB | per-resource body capture ceiling |
| `max_network_requests_recorded` | 400 | evidence size ceiling |
| `respect_robots` | true | `robots.txt` disallow on the target path aborts with a clear error |
| `user_agent` | `WebLens/<version> (+https://…; passive analyzer)` | identifiable, honest |

Request pattern per scan: one `robots.txt` fetch, one HTTP probe of the target, one TLS handshake,
one DNS resolution, one browser navigation (plus the subresources the page itself requests). No
crawling, no path enumeration, no repeated retries beyond a single redirect-following attempt.

## Configuration

`pydantic-settings` `Settings` object, env prefix `WEBLENS_`, loaded once and injected via
`Depends(get_settings)`. Every tunable in the table above is a field. Nothing reads `os.environ`
directly outside `config.py`.

## Logging

`logging.py` configures one root handler with a structured formatter (key=value or JSON, selected by
`WEBLENS_LOG_FORMAT`). All logs carry `scan_id` and `stage` via a `contextvars`-backed filter, so a
scan can be traced without threading a logger through every call. Analyzer failures log at
`warning` with the exception type and analyzer id; unexpected pipeline failures log at `error` with
traceback. Target response bodies are never logged; evidence excerpts are truncated and only appear
in the result payload.

## Error model

```
WebLensError(code: ErrorCode, message, detail?, retryable: bool)
  ├─ TargetValidationError    → 400  INVALID_URL
  ├─ TargetBlockedError       → 403  BLOCKED_TARGET / ROBOTS_DISALLOWED
  ├─ CollectionError          → 502  DNS_FAILURE / CONNECT_FAILURE / TLS_FAILURE / NAVIGATION_TIMEOUT
  ├─ BrowserUnavailableError  → 503  BROWSER_UNAVAILABLE
  ├─ RateLimitedError         → 429  RATE_LIMITED
  ├─ NotFoundError            → 404  SCAN_NOT_FOUND
  └─ ResultExpiredError       → 410  RESULT_EXPIRED
```

`api/problems.py` maps these to RFC 9457 `application/problem+json`. Unhandled exceptions become
`500 INTERNAL_ERROR` with a generated incident id that is also logged — no stack traces over the
wire.

Failures *inside* a scan do not become HTTP errors: they are recorded as `ScanError` entries on the
result and reflected in section statuses (A7). A scan only fails outright when collection cannot
produce a navigable page at all.

## Exposure posture (no auth in V1, by requirement)

The API accepts an arbitrary URL and fetches it, which makes it a request-forwarding surface. V1
mitigations, all implemented in `collection/target.py` and `config.py`:

- Bind to `127.0.0.1` by default; CORS allowlist limited to the dev frontend origin.
- Reject non-`http(s)` schemes, credentials in URL, and non-default ports outside an allowlist.
- Resolve DNS first and reject loopback, private, link-local, CGNAT, multicast, reserved ranges and
  known cloud metadata addresses — before any connection, and re-checked on every redirect hop.
- Cap redirects (default 5) and reject cross-scheme downgrade chains for evidence purposes (recorded
  as a finding rather than followed blindly).
- Response bodies are never echoed back verbatim; only bounded, sanitized excerpts.

This is documented in the README as a deployment caveat: **WebLens V1 is a local developer tool and
must not be exposed to an untrusted network without adding authentication and egress controls.**
