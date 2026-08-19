# 4. Scanner architecture

The scanner is the only part of WebLens that touches the target. It collects once, broadly, into a
single immutable `RawEvidence` object; analysis happens afterwards, offline.

## Why collect-then-analyze

- Analyzers stay pure and unit-testable from committed fixtures (no network in tests).
- The target is contacted with one predictable, polite request pattern regardless of how many
  analyzers exist.
- A fixture recorded today can validate analyzer changes forever (regression safety net).
- Adding an analyzer never adds load on the target.

## Stage sequence

Stages are declared in `orchestration/stages.py` with a `weight` used for honest progress reporting.
Each stage is independently fallible and records its own outcome in `CollectionMeta.stages`.

| # | Stage | Produces | On failure |
|---|-------|----------|-----------|
| 1 | `validate` | normalized target, guard verdict | abort scan (400/403) |
| 2 | `dns` | A/AAAA/CNAME, resolved IPs | continue; IP-dependent findings become `unable_to_verify` |
| 3 | `robots` | robots.txt text, allow/deny for path | `respect_robots` + disallow → abort (403); fetch error → continue |
| 4 | `http_probe` | status, header sets for every hop, redirect chain, set-cookie, raw pre-JS HTML | abort if no response at all |
| 5 | `tls` | protocol, cipher, cert subject/issuer/validity/SAN count | continue; TLS findings `unable_to_verify` |
| 6 | `browser_launch` | browser + context (fixed viewport, UA, timezone) | skip all browser stages; sections needing runtime → `unavailable` |
| 7 | `navigate` | final URL, response status, console/error stream start, network recording | abort if navigation yields no document |
| 8 | `dom_capture` | rendered HTML, head/meta inventory, element inventories, headings, forms, landmarks | section-level degradation |
| 9 | `runtime_capture` | runtime globals, module/loader signals, service worker, storage key names | degradation |
| 10 | `style_capture` | computed style samples, palette, loaded fonts, radius/shadow/spacing distributions, animation usage | degradation |
| 11 | `perf_capture` | navigation/paint timing, LCP, CLS, long tasks, resource entries | degradation |
| 12 | `network_capture` | finalized request/response ledger, sizes, protocols, cache headers | degradation |
| 13 | `a11y_capture` | axe-core results (injected, read-only) | degradation |
| 14 | `responsive_probe` | layout metrics at declared widths (no reload; viewport resize only) | degradation |
| 15 | `screenshot` | viewport + optional full-page PNG | degradation |
| 16 | `analyze` | all analyzer runs | per-analyzer isolation |
| 17 | `assemble` | `AnalysisResult` | abort only on internal error |

Total wall-clock is bounded by `total_scan_budget_ms`. When the budget is exhausted, remaining
collection stages are marked `skipped` with reason `budget_exhausted` and dependent sections report
that explicitly. No stage is allowed to silently produce partial data without recording it.

## Browser collection details

- One Playwright instance and one browser (Chromium) per process, created in the FastAPI lifespan and
  reused; a fresh **context** per scan for isolation (no cookie/cache bleed between scans).
- Context configuration is recorded in the result so measurements are interpretable: viewport
  1440×900 @ dpr 1, UA string, locale `en-US`, timezone `UTC`, `reduced-motion: no-preference`,
  JS enabled, cache disabled for the main navigation.
- Navigation: `goto(url, wait_until="domcontentloaded")`, then a bounded settle wait — network-idle
  with a hard ceiling (`settle_timeout_ms`, default 5000) — then capture. Both the wait strategy and
  the actual settle outcome are recorded, because performance numbers are meaningless without them.
- In-page capture uses versioned JS files in `collection/probes/`, injected via `page.evaluate`. They
  are read-only: they query the DOM, `getComputedStyle`, and `performance` entries. They do not click,
  submit, scroll-hijack, or mutate the page. Full-page screenshots are the one exception — Chromium
  scrolls internally to capture, which is a rendering operation, not an interaction.
- `axe-core` is injected as a vendored, pinned script for the accessibility stage.

## Sampling strategy for style capture

Computed styles cannot be read for every node on a large page within budget. The probe samples
deterministically so results are reproducible:

- All elements in document order, capped at `max_style_samples` (default 1500).
- Plus a guaranteed set: `html`, `body`, first `h1`-`h3`, first 20 `a`/`button`/`input`, elements
  matching `[class*="card"]`, `header`, `nav`, `main`, `footer`, `section`.
- Per property, values are aggregated into frequency distributions with element counts, and the
  sample size + cap-hit flag are recorded so the design analyzer can state coverage honestly.

## Network ledger

Every request/response pair observed during navigation is recorded (capped) with: URL, method,
resource type, status, protocol (`h2`/`h3`/`http/1.1`), MIME type, transfer + decoded size, timing,
`from_cache`, initiator type, whether it is same-site/cross-site, and selected response headers
(cache/CORS/security only — never `set-cookie` values from third parties, only their presence).

## Failure isolation

```python
for analyzer in registry.enabled_for(request):
    try:
        section_parts.append(await run_with_timeout(analyzer, ctx, timeout=analyzer.timeout_ms))
    except Exception as exc:                       # narrowed to Exception, never BaseException
        errors.append(ScanError.from_analyzer(analyzer, exc))
        mark_section_degraded(analyzer.section, reason=str(type(exc).__name__))
```

Every analyzer runs in its own guarded call with its own timeout. A crash, a timeout, or a missing
evidence dependency all produce the same visible outcome: that analyzer's contribution is absent, the
section status becomes `partial` or `unavailable` with a machine-readable reason, and the rest of the
report is unaffected (A7).

## What the scanner will not do

No form submission, no login attempts, no header/parameter fuzzing, no path or subdomain
enumeration, no vulnerability probes, no concurrent request floods, no bypassing of bot protection,
no ignoring `robots.txt` when `respect_robots` is on. Detected access restrictions (403/429/challenge
pages) are reported as observations, not obstacles to work around.
