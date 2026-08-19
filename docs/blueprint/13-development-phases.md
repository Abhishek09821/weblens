# 13. Development phases

Each phase ends with something demonstrable and tested. No phase leaves placeholder data in
production code — an unimplemented analyzer reports `not_implemented`, which is a real state the UI
renders honestly.

## Phase 0 — Blueprint + skeleton (this phase)

- Blueprint documents 1–15.
- Repo scaffolding, both toolchains installable and runnable.
- Backend: config, logging, domain models, target guard (SSRF-safe), HTTP probe, job store, pipeline,
  stage progress, analyzer registry, API surface (health, capabilities, scans CRUD, SSE), problem
  mapping. One **pilot analyzer** (`seo.metadata`) proving the evidence → finding → section → API path.
- Frontend: Vite/React/TS/Tailwind/shadcn shell, typed API client with zod, IndexedDB repository with
  migrations, prefs, analyze screen with real stage progress, dashboard with 8 section panels,
  report generation framework with the SEO renderer + `analysis.json` + zip.
- Tests: guard table, pilot analyzer four-case suite, API lifecycle, IndexedDB round-trip/delete,
  report render.

Exit criteria: `make check` green; a real scan of a public URL returns a valid result; the result
survives a browser restart; `complete-report.zip` downloads.

## Phase 1 — Browser collection

Playwright lifecycle in the app lifespan, per-scan context, navigation with recorded wait strategy,
DOM capture, runtime globals, network ledger, console capture, screenshots, responsive probe,
`capture_evidence.py`, the full fixture corpus. Sections still report `not_implemented`; the evidence
is real and inspectable via a debug endpoint (dev-only, gated by `settings.debug`).

Exit criteria: a fixture can be captured for every corpus entry; degraded collection (browser missing)
still yields a scan.

## Phase 2 — Security section end-to-end

`security.headers` (with real CSP parsing), `security.cookies`, `security.tls`,
`security.mixed_content`, `security.third_party`, `security.exposure`, then `security.scoring` with the
full doc-11 rule table, band caps, and N/A arithmetic. `security.md` renderer. Frontend security panel
with the rule table and methodology link.

Chosen first because it is the section with a score, the strictest correctness requirements, and the
most reusable evidence plumbing (headers/cookies/network).

Exit criteria: scoring suite green including boundary and cap cases; hardened and bare fixtures
produce expected scores; UI never uses verdict language.

## Phase 3 — Technology, architecture, network

Signature engine + data files, `technology.stack/framework/language/styling`,
`architecture.rendering/platform/runtime`, `network.resources/third_parties`. Static-vs-rendered node
delta for rendering inference. Technology cards and network tables in the UI.

Exit criteria: SPA/SSR/static fixtures classified correctly; every version claim either captured from
a signature or `not_determinable`; no domain literals outside signature data.

## Phase 4 — Design section

Style sampling probe, distributions, palette, typography from `document.fonts`, spacing/radius/shadow
scales, media inventory, motion usage, responsive metrics, then `design.interpretation` producing only
`Interpretation` objects. Design panel with swatches, type scale, and a visually separated
interpretation block.

Exit criteria: sample coverage reported with every design claim; facts and interpretation never share
a container in UI or markdown.

## Phase 5 — Performance and accessibility

Performance entries (TTFB/FCP/LCP/CLS/long tasks), resource summary, run context surfaced everywhere.
Vendored pinned axe-core injection, violations by impact, structural observations. No scores in either
section.

Exit criteria: every metric has a unit and a run-context caveat; axe engine version recorded in the
result; a11y section survives axe injection failure as `unavailable`.

## Phase 6 — Reports and library polish

All seven markdown renderers, bundle README, screenshots in the zip, per-section download, scan
library (search/filter/sort/compare-by-host), retention preference, quarantine UI.

Exit criteria: report snapshots stable; delete removes every trace; secrets grep test green.

## Phase 7 — Optional AI explanation layer

Provider protocol with `NullProvider` default, prompt construction from findings only, grounding
filter that drops uncited sentences, `dropped_claims` surfaced in the UI, hard separation from
`AnalysisResult`.

Exit criteria: with AI disabled (default) nothing changes anywhere; with a stub provider returning an
ungrounded claim, the claim is dropped and reported; no AI text is ever persisted as a finding.

## Phase 8 — Hardening

Budget/timeout tuning, memory and browser-crash recovery, structured log review, per-host rate
limiting, error-message review pass, `docs/limitations.md` completeness audit, accessibility audit of
WebLens itself, performance of large-result rendering (virtualized network table).

## Sequencing rationale

Collection before any analyzer (analyzers without evidence are guesses). Security before design
(strictest correctness bar first, and it exercises the header/cookie/network plumbing every later
section reuses). Design before performance (design consumes the same style/DOM capture, so the probe
gets battle-tested by a section that is tolerant of missing samples). AI last, because it must be
provably removable.
