# 15. Technical risks and limitations

Two categories: **risks** (things that could go wrong in the build) and **limitations** (things the
product structurally cannot do, which must be stated in its output rather than papered over).

## Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|-----------|
| R1 | Bot protection / WAF challenges (Cloudflare, Akamai, PerimeterX) return an interstitial instead of the site | Every section analyzes the challenge page and reports nonsense about the target | Detect challenge signatures (status 403/503 + known markers + tiny DOM) and set scan status to `completed_with_errors` with `ACCESS_RESTRICTED`; sections report `unable_to_verify`. Never attempt evasion (A6) |
| R2 | JS-heavy apps still rendering when capture starts | Under-reported DOM, wrong perf numbers, missed frameworks | Bounded network-idle settle with recorded outcome (`settle_reached`); every affected finding carries the wait strategy as a limitation; static-vs-rendered delta makes late hydration visible rather than invisible |
| R3 | Playwright browser missing or crashing | Half the evidence slots empty | `browser.available` on `/health` as pre-flight; browser stages degrade to `unavailable` with reason; process-level recovery relaunches the browser once per scan; HTTP-only sections (SEO, headers, TLS) still produce results |
| R4 | Single-process in-memory job store | Results lost on restart; no horizontal scale | Accepted for V1 by design (browser owns persistence); client persists immediately then `DELETE`s; store sits behind a `JobStore` protocol for a future durable implementation |
| R5 | Unauthenticated API that fetches arbitrary URLs (SSRF surface) | Could be used to probe internal networks if exposed | Loopback bind by default, CORS allowlist, pre-connection DNS resolution with private/reserved-range denial re-checked on every redirect hop, port allowlist, no credentials in URL, bounded redirects. README states plainly that V1 must not be exposed to an untrusted network without auth and egress controls |
| R6 | Memory pressure from large pages (huge DOM, many resources) | Browser or API OOM | Caps on style samples, recorded requests, captured body bytes, and evidence excerpt length; caps are reported when hit (`cap_hit: true`) so numbers are never silently truncated |
| R7 | Technology signature staleness | Missed or wrong detections over time | Signatures are data files with ids and provenance notes, not code; multi-signal corroboration required for `verified`; single weak signals yield `inferred` with the signal shown |
| R8 | Minified/bundled code defeats framework and version detection | Version claims impossible | Version is `not_determinable` unless a signature explicitly captures it. Never inferred from a filename hash or bundle size |
| R9 | IndexedDB quota exceeded or storage disabled | Persistence requirement silently unmet | Pre-write quota estimate, retry without screenshots, in-memory repository fallback behind the same interface, explicit "session-only" banner. Never fails silently |
| R10 | Report snapshot tests become churn-heavy | Team stops updating them thoughtfully | Renderers are deterministic and small; snapshots are per-section, so a design change touches one file |
| R11 | AI layer leaking unsupported claims into perceived facts | Violates the product's core promise | AI never runs on the scan path, receives only findings, output stored separately from `AnalysisResult`, sentences without a resolvable finding citation are dropped and counted in `dropped_claims`; default provider is `NullProvider` |
| R12 | Contract drift between Pydantic and TypeScript | Runtime shape errors in the UI | `contracts/openapi.json` committed + regenerated in CI with a clean-tree check; zod validates at both boundaries; a fixture-based parse test |
| R13 | Python 3.14 default on dev machines vs Playwright's supported range | Confusing install failures | `requires-python = ">=3.12,<3.13"` fails fast at install; `make setup` selects `python3.12` explicitly |
| R14 | Scanning cost tempting a "cache results per URL" shortcut | Backend becomes the data store the design forbids | TTL is short by design and results are deleted on client confirmation; caching by URL is called out here as an explicitly rejected optimization |
| R15 | Target sites behind geo/consent walls return a consent page | Analysis describes the consent page | Same handling as R1: detected as restricted access, reported, not bypassed. Consent walls are never auto-accepted (clicking would violate passive-only) |

## Limitations (stated in the product, not just here)

These are rendered in `/about`, embedded in every generated report, and carried in
`limitations[]` on results and sections. `docs/limitations.md` is the canonical list.

**Scope of observation**

1. One URL per scan. No crawling, so findings describe that page, not the whole site.
2. One cold run at one moment, from one network location, with one viewport and one browser
   (Chromium). Results vary between runs; performance numbers especially.
3. Only publicly reachable, unauthenticated content. No logged-in states, no paywalled pages.
4. Server-side implementation details (language, framework, database, infrastructure topology) are
   usually **not determinable** from outside. When headers disclose them, that disclosure is itself the
   finding.

**Performance**

5. Lab measurement, not field data: no CrUX, no real-user metrics, no throttling by default. Not
   comparable to Lighthouse scores, and no score is produced.
6. LCP/CLS are captured at a bounded settle point; interactions after that point are not observed, so
   metrics that depend on user input (INP) are out of scope.

**Accessibility**

7. Automated rules (axe-core) detect a subset of WCAG issues. A clean result does **not** mean the site
   is accessible; conformance requires manual testing with assistive technologies and expert review.
8. Only the initial rendered state is checked — no modal, menu, or form-error states.

**Security**

9. Passive and external only: configuration and headers, never application logic, dependencies,
   server-side controls, or data handling. No exploitation, no authentication testing, no fuzzing.
10. The score reflects observable configuration on one page. It cannot establish that a site is secure
    or insecure, and it is not a compliance rating.
11. TLS observations describe one negotiated connection from this client; they are not a full cipher
    suite or certificate chain audit.
12. Source-map references are reported as observed references; the `.map` files are not fetched.

**Design**

13. Style data comes from a capped, deterministic sample of elements; coverage is reported alongside
    every design finding.
14. Responsive behaviour is observed by resizing the viewport without reload, so scripts that only
    branch at load time may not be exercised.
15. Style classifications ("modern", "minimal", "SaaS-like") are interpretations derived from measured
    values, always labelled as such, never presented as facts.

**Technology**

16. Detection requires an observable signal. Absence of a signal means "not detected", never "not
    used" — server-rendered, self-hosted, or aggressively bundled technologies are frequently
    invisible from outside.
17. Versions are reported only when a signature captures one explicitly.

**Persistence**

18. Scans live in this browser profile only. They are not synced, not shared, and clearing site data
    or deleting a scan removes them permanently. There is no server copy to restore from.
