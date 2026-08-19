# 5. Analyzer module design

## The contract

```python
class Analyzer(Protocol):
    id: str                          # stable, e.g. "security.headers"
    section: SectionKey
    version: str                     # bump when logic changes; recorded per run
    requires: frozenset[EvidenceSlot]  # e.g. {EvidenceSlot.HTTP, EvidenceSlot.DOM}
    depends_on: frozenset[str]       # analyzer ids whose findings this one consumes
    timeout_ms: int

    def analyze(self, ctx: AnalyzerContext) -> AnalyzerOutput: ...
```

```python
@dataclass(frozen=True)
class AnalyzerContext:
    evidence: RawEvidence            # immutable
    findings: FindingIndex           # read-only view of findings already produced
    settings: AnalyzerSettings       # thresholds only, no I/O handles

@dataclass
class AnalyzerOutput:
    findings: list[Finding]
    interpretations: list[Interpretation] = field(default_factory=list)
    data: SectionPayload | None = None      # typed per-section extras
    limitations: list[str] = field(default_factory=list)
```

Properties that make this work:

- **Pure and synchronous.** No `async`, no clients, no clock reads except `evidence.collected_at`.
  Determinism is testable: same evidence in, byte-identical findings out.
- **Declarative dependencies.** `requires` lets the registry skip an analyzer with a precise reason
  (`missing_evidence: dom`) instead of letting it throw. `depends_on` gives the aggregator ordering
  (topological sort at registry build time, cycle = startup error).
- **No I/O available.** `analyzers/` may not import `collection/` or `httpx` (enforced by an
  import-linter rule in CI).

## Helper library (`analyzers/base.py`)

Shared builders remove the duplication that would otherwise appear in 25+ modules:

| Helper | Purpose |
|--------|---------|
| `finding(...)` | constructs a `Finding` with id namespacing and required-evidence validation |
| `not_detected(...)` / `not_determinable(...)` / `unable_to_verify(...)` | the three explicit negative outcomes, each requiring a reason |
| `header_evidence(name)` / `dom_evidence(path)` / `style_evidence(prop)` | `EvidenceRef` factories with consistent `source` paths |
| `SignatureMatcher` | shared multi-signal matching used by technology/framework/styling/platform analyzers |
| `version_from(patterns)` | extracts a version string only when a pattern captures one; otherwise value stays `None` and status stays `verified` for presence, `not_determinable` for version |

## Confidence → status derivation (single place, `base.py`)

| Signal situation | `confidence` (internal) | `status` (user-facing) |
|------------------|------------------------|------------------------|
| Direct authoritative observation (header present, global object present, font actually loaded) | `definitive` | `verified` |
| Two or more independent corroborating signals | `strong` | `verified` |
| One weak/ambiguous signal (e.g. filename pattern only) | `moderate` | `inferred` |
| Circumstantial only (utility-class shape, generic bundle name) | `weak` | `inferred` |
| Evidence present, signal absent | n/a | `not_detected` |
| Property is not observable from the outside by nature | n/a | `not_determinable` |
| Required evidence slot missing due to collection failure | n/a | `unable_to_verify` |

Consequence: the UI and reports show `verified` vs `inferred`, and `inferred` is always accompanied
by the signal that produced it. A percentage is never shown next to a claim (A5).

## Module inventory

### Technology (`section: technology`)

| id | Evidence used | Output | Notes |
|----|---------------|--------|-------|
| `technology.stack` | http headers, dom, network, runtime | detected products grouped by category (CDN, analytics, tag manager, CMS, e-commerce, font provider, error tracking) | signature-data driven |
| `technology.framework` | runtime globals, dom attrs (`data-reactroot`, `__NEXT_DATA__`, `id="__nuxt"`, `ng-version`, Svelte class hashes), script URLs, bundle strings | framework + version when a signature captures one | version is `not_determinable` unless captured |
| `technology.language` | response headers (`Server`, `X-Powered-By`), cookie name conventions, URL extensions, error page signatures | server-side language/runtime | most sites are `not_determinable`; that is the expected answer, not a failure |
| `technology.styling` | stylesheet URLs, class-name shape statistics, CSS custom property names, `@layer`/preflight fingerprints | CSS framework/methodology | utility-class ratio is a statistic, reported as such |

### Design (`section: design`)

| id | Evidence used | Output |
|----|---------------|--------|
| `design.color` | computed style distributions, screenshot palette (optional) | background/text/accent palette with element counts, contrast pairs observed, gradient usage |
| `design.typography` | `document.fonts` entries, computed `font-family`/`size`/`weight`/`line-height` distributions | actually-loaded families, observed weights, measured type scale |
| `design.layout` | computed `display`/`grid-template`/`flex`, container widths, spacing distributions, radius/shadow distributions, responsive metrics | layout system usage, spacing scale, radius/shadow inventory, breakpoint behavior observed |
| `design.media` | dom inventories, network ledger | SVG/img/video/picture counts, formats (avif/webp), lazy-loading usage, icon strategy |
| `design.motion` | computed `transition`/`animation`, CSS keyframe count, animation-library signatures | animation/transition usage counts |
| `design.interpretation` | **findings only** (`depends_on` the five above) | `Interpretation[]` such as "dark, high-radius, gradient-heavy visual language" — emits zero `Finding`s by construction |

`design.interpretation` is the only module allowed to produce subjective statements, and it can only
produce `Interpretation` objects, each citing finding ids. That structural split is how "observed
facts" and "interpretation" stay separated in every output surface.

### Security (`section: security`) — passive only

| id | Evidence used | Output |
|----|---------------|--------|
| `security.headers` | final-hop response headers (+ all hops for HSTS/redirects) | presence/quality findings for CSP (with directive parsing), HSTS, XCTO, Referrer-Policy, Permissions-Policy, frame controls, COOP/COEP/CORP |
| `security.cookies` | `set-cookie` on all hops + `context.cookies()` | per-cookie `Secure`/`HttpOnly`/`SameSite`/`Domain` scope/expiry observations |
| `security.tls` | tls probe | protocol version, cipher, cert issuer/validity window/days remaining, SAN count |
| `security.mixed_content` | dom refs, network ledger, console | active vs passive mixed content, insecure form actions, `http://` subresource references |
| `security.third_party` | network ledger, dom scripts | cross-origin script count/domains, SRI coverage, `crossorigin` usage, breadth of external execution surface |
| `security.exposure` | headers, dom comments, network | version disclosure in `Server`/`X-Powered-By`/`X-AspNet-Version`, source-map references, debug-ish headers |
| `security.scoring` | `depends_on` all of the above | `SecurityScore` per [11](11-security-scoring-methodology.md) |

### Performance (`section: performance`)

| id | Output |
|----|--------|
| `performance.timings` | TTFB, DCL, load, FCP, LCP (+element), CLS, long-task count/total blocking estimate, DOM interactive |
| `performance.resources` | request count and bytes by type/domain, compression coverage, cache-header coverage, render-blocking counts, largest resources |

No performance score, no grade, no synthetic "opportunities" (A4). Every metric carries the run
context (single cold lab run, fixed viewport, no throttling by default) as a limitation.

### Accessibility (`section: accessibility`)

| id | Output |
|----|--------|
| `accessibility.axe` | axe-core violations grouped by impact, with rule id, help URL, node count, sample selectors |
| `accessibility.structure` | `html[lang]`, document title, landmark presence, heading order/skips, image alt coverage, form-label coverage, focusable-element count, positive `tabindex` count, viewport meta zoom restrictions |

Limitation carried in every output: automated rules cover a subset of WCAG; no score is produced.

### SEO (`section: seo`)

| id | Output |
|----|--------|
| `seo.metadata` | title, meta description (with lengths), canonical, `robots` meta, `hreflang`, Open Graph, Twitter card, favicon set |
| `seo.indexability` | robots.txt directives for the path, `X-Robots-Tag`, canonical self-reference, redirect chain shape, sitemap references |
| `seo.structured_data` | JSON-LD blocks parsed to `@type` inventory, microdata/RDFa presence, syntax validity of each block |

### Network (`section: network`)

| id | Output |
|----|--------|
| `network.resources` | full ledger summary: per-domain counts/bytes, protocol mix, MIME mix, status-code mix, cache hit ratio |
| `network.third_parties` | distinct third-party domains classified by signature category, first-party vs third-party byte split, cookie-setting third parties (presence only) |

### Architecture (`section: architecture`)

| id | Output |
|----|--------|
| `architecture.rendering` | SSR/SSG/CSR/hydration signals: static-HTML vs rendered-DOM node delta, hydration payload presence (`__NEXT_DATA__`, `__NUXT__`, `self.__next_f`), `noscript` fallback content |
| `architecture.platform` | hosting/CDN/edge indicators from headers (`server`, `via`, `x-vercel-id`, `cf-ray`, `x-amz-cf-id`, `x-served-by`), DNS CNAME chain, asset domain patterns |
| `architecture.runtime` | HTTP protocol used, service worker registration, WASM requests, module vs classic scripts, storage APIs touched (key names only), console error/warning counts, redirect topology |

The static-vs-rendered node delta is the honest core of rendering detection: a large delta with a
hydration payload supports "client-rendered/hydrated"; a small delta with content in the initial HTML
supports "server-rendered or pre-rendered". Distinguishing SSR from SSG from the outside is often
impossible, so `architecture.rendering` emits `not_determinable` for that distinction unless a
platform header (e.g. an explicit cache-status/prerender header) settles it.

## Adding an analyzer (the whole checklist)

1. New module under `analyzers/<section>/`, implementing the protocol.
2. Register it in `orchestration/registry.py` (id, section, requires, depends_on).
3. Add a fixture-based unit test asserting statuses, not just values.
4. Add its findings to the section renderer if a new visual shape is needed.
5. Document any new limitation string in `docs/limitations.md`.

No changes to the pipeline, API, or frontend plumbing are required — that is the point of the design.
