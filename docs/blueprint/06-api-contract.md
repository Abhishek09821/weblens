# 6. API contract design

Base path `/api/v1`. JSON only. Errors are `application/problem+json` (RFC 9457).

**Field naming: `snake_case` on the wire, in Pydantic, and in TypeScript.** No camelCase conversion
layer — a translation layer is a place for drift and bugs to hide, and it makes evidence `source`
paths (which are literal Python/DOM paths) inconsistent with the types that carry them.

## Versioning

Two independent versions travel with every result:

- `schema_version` (`"1.0"`) — shape of `AnalysisResult`. Bumped on breaking changes; IndexedDB
  migrations key off it.
- `engine_version` — detection logic version (backend package version). Two scans of the same site
  with different engine versions are legitimately comparable only with this in view.

The URL path version (`/api/v1`) changes only for transport-breaking changes.

## Endpoints

### `GET /health`

Liveness + browser readiness. Used by the frontend to warn before a scan is attempted.

```json
{
  "status": "ok",
  "engine_version": "0.1.0",
  "schema_version": "1.0",
  "uptime_seconds": 1284.4,
  "browser": { "available": true, "name": "chromium", "version": "141.0.7390.37" },
  "active_scans": 0
}
```

`browser.available` is `false` (with `version: null`) when Playwright browsers are not installed;
`status` stays `ok` because the API is up. The frontend surfaces this as a pre-flight warning.

### `GET /api/v1/capabilities`

Lets the frontend render honest section states without hardcoding what the backend can do.

```json
{
  "engine_version": "0.1.0",
  "schema_version": "1.0",
  "sections": ["design","technology","security","performance","accessibility","seo","architecture","network"],
  "analyzers": [
    { "id": "seo.metadata", "section": "seo", "version": "1.0.0", "implemented": true,
      "requires": ["http"], "description": "Document metadata observed in the served HTML." }
  ],
  "stages": [ { "key": "http_probe", "label": "Fetching document", "weight": 10, "optional": false } ],
  "limits": { "navigation_timeout_ms": 30000, "total_scan_budget_ms": 90000, "result_ttl_seconds": 900,
              "max_concurrent_scans": 2, "respect_robots": true }
}
```

`implemented: false` is a first-class state during phased development: the section renders
"Not implemented in this build" rather than an empty panel or invented content.

### `POST /api/v1/scans`

```json
{
  "url": "https://example.com",
  "options": {
    "include_screenshot": true,
    "include_full_page_screenshot": false,
    "viewport": { "width": 1440, "height": 900 },
    "responsive_widths": [390, 768, 1440],
    "sections": null
  }
}
```

`sections: null` means all. Unknown option fields are rejected (`extra="forbid"`) — silent option
typos are worse than a 422.

`202 Accepted`:

```json
{
  "scan_id": "01JB2K9ZQ4T7M8V6XN3H5RCWDA",
  "status": "queued",
  "requested_url": "https://example.com",
  "normalized_url": "https://example.com/",
  "created_at": "2026-08-19T10:12:03.114Z",
  "links": { "self": "/api/v1/scans/01JB…", "events": "/api/v1/scans/01JB…/events", "result": "/api/v1/scans/01JB…/result" }
}
```

Scan ids are ULIDs: sortable by creation time, URL-safe, no coordination needed.

### `GET /api/v1/scans/{scan_id}` — job state

```json
{
  "scan_id": "01JB…",
  "status": "running",
  "created_at": "…", "started_at": "…", "finished_at": null,
  "progress": {
    "current_stage": "style_capture",
    "current_stage_label": "Sampling computed styles",
    "completed_weight": 62, "total_weight": 100,
    "stages_completed": 9, "stages_total": 17
  },
  "stages": [ { "key": "http_probe", "status": "completed", "duration_ms": 412, "error": null } ],
  "problem": null
}
```

`ScanStatus`: `queued | running | completed | completed_with_errors | failed | cancelled`.
Progress is computed from declared stage weights actually completed. There is no interpolation and
no time-based estimate (the requirement "no fake progress" is enforced by simply not having a
mechanism to fake it).

### `GET /api/v1/scans/{scan_id}/events` — SSE

```
event: stage
data: {"scan_id":"01JB…","stage":"navigate","status":"started","at":"…"}

event: progress
data: {"scan_id":"01JB…","completed_weight":31,"total_weight":100,"current_stage":"dom_capture"}

event: status
data: {"scan_id":"01JB…","status":"running"}

event: done
data: {"scan_id":"01JB…","status":"completed_with_errors","result_url":"/api/v1/scans/01JB…/result"}

event: error
data: {"type":"about:weblens/problem/navigation-timeout","code":"NAVIGATION_TIMEOUT","title":"…","detail":"…"}
```

Emitted from the same progress channel the pipeline writes to, so events cannot disagree with
`GET /scans/{id}`. A heartbeat comment (`: ping`) every 15s keeps proxies from closing the stream.
The stream terminates after `done` or `error`. Late subscribers receive the current state as a
synthetic snapshot first, so a reconnect never loses the scan.

### `GET /api/v1/scans/{scan_id}/result`

`200` with the full `AnalysisResult` (see [07](07-pydantic-models.md)) once the scan reached a
terminal state. `409` if still running, `410 RESULT_EXPIRED` once evicted by TTL/LRU,
`404 SCAN_NOT_FOUND` if never known.

### `DELETE /api/v1/scans/{scan_id}`

`204`. Client calls this after a successful IndexedDB write. Idempotent — deleting an unknown id is
also `204`, because the desired end state (no server copy) holds either way.

### `POST /api/v1/ai/explain` (optional layer)

```json
{ "scan_id": "01JB…", "sections": ["design","architecture"], "audience": "engineer" }
```

`501 AI_DISABLED` when no provider is configured, which is the default. When enabled, the response is
explicitly separated from facts:

```json
{
  "scan_id": "01JB…",
  "provider": "…", "model": "…", "generated_at": "…",
  "narratives": [
    { "section": "design", "text": "…", "grounded_in": ["design.color:palette.background", "design.layout:radius.distribution"] }
  ],
  "dropped_claims": [ { "text": "Built with Webflow", "reason": "no_matching_finding" } ]
}
```

Grounding rule (A9): the AI is given only findings + interpretations, and every sentence it produces
must cite at least one finding id that exists in the result. `ai/grounding.py` drops sentences whose
citations are missing or unresolvable and records them in `dropped_claims`, which is rendered in the
UI as a transparency detail rather than hidden. Narratives are never written into `AnalysisResult`
and never persisted as findings.

## Status code policy

| Code | When |
|------|------|
| 202 | scan accepted |
| 200 | state/result/capabilities read |
| 204 | delete |
| 400 | malformed URL (`INVALID_URL`) |
| 403 | blocked target (`BLOCKED_TARGET`), robots disallow (`ROBOTS_DISALLOWED`) |
| 404 | unknown scan id |
| 409 | result requested while running |
| 410 | result evicted |
| 422 | request body fails schema validation |
| 429 | admission control (`RATE_LIMITED`), with `Retry-After` |
| 500 | unexpected (`INTERNAL_ERROR`, incident id) |
| 501 | AI layer disabled |
| 502 | target unreachable (`DNS_FAILURE`, `CONNECT_FAILURE`, `TLS_FAILURE`, `NAVIGATION_TIMEOUT`) |
| 503 | browser unavailable (`BROWSER_UNAVAILABLE`) |

Problem shape:

```json
{
  "type": "about:weblens/problem/blocked-target",
  "title": "Target is not publicly routable",
  "status": 403,
  "detail": "Host resolves to 127.0.0.1, which is in a blocked range (loopback).",
  "code": "BLOCKED_TARGET",
  "instance": "/api/v1/scans",
  "retryable": false
}
```

Important distinction: **a target that responds with an error status is not an API error.** A 404 or
403 from the scanned site is data — it is recorded in `TargetInfo.http_status` and the scan proceeds
as far as it can. Only failure to obtain any response produces a 502.

## Contract generation flow

```
backend/scripts/export_openapi.py  →  contracts/openapi.json
                                   →  openapi-typescript  →  frontend/src/types/api.generated.ts
```

`make contracts` runs both. CI runs it and fails if the working tree changes, which makes contract
drift a build error rather than a runtime surprise. Hand-authored zod schemas in
`frontend/src/types/analysis.ts` validate payloads at runtime; a test asserts they accept the
committed fixture result and reject a mutated one.
