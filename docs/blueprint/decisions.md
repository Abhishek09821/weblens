# Decision record

Short entries, one per non-obvious choice, with the tradeoff we accepted. Reversal cost noted so
future changes are informed rather than archaeological.

## D1 — Collect once into `RawEvidence`, then run pure analyzers

**Alternative:** each analyzer queries the live page itself.
**Chosen because:** analyzers become deterministic pure functions (unit-testable from committed
fixtures, cannot leak requests), and the target sees one predictable request pattern no matter how many
analyzers exist.
**Cost:** the evidence model must anticipate what analyzers need; adding a new signal means touching
the collection layer and re-capturing fixtures.
**Reversal:** expensive. This shapes the whole backend.

## D2 — Reports rendered client-side in TypeScript

**Alternative:** Jinja templates in the backend.
**Chosen because:** results are persisted in IndexedDB and must be exportable with the backend
stopped; a second renderer would be duplicate logic that drifts.
**Cost:** no `curl`-able report endpoint in V1.
**Reversal:** cheap — renderers are pure functions of `AnalysisResult`.

## D3 — `snake_case` on the wire and in TypeScript

**Alternative:** camelCase in the frontend with a mapping layer.
**Chosen because:** a mapping layer is a drift and bug surface, and evidence `source` strings are
literal Python/DOM paths that would look inconsistent next to camelCase fields.
**Cost:** violates common JS style convention.
**Reversal:** cheap but touches every component.

## D4 — Only security is scored

**Alternative:** grades per section, as most site-audit tools do.
**Chosen because:** scores for design, technology, or architecture would be invented weightings
presented as measurements. Security scoring is defensible only because every rule is publicly
documented and evidence-linked.
**Cost:** less "dashboard candy"; users expecting per-section grades must read observations.
**Reversal:** trivial to add, hard to justify.

## D5 — Confidence is internal; status is user-facing

**Alternative:** show "85% confident React".
**Chosen because:** a percentage next to an uncertain claim reads as authority and launders guesses
into facts. `verified` vs `inferred` (with the signal shown) is honest and actionable.
**Cost:** loses a granularity some users like.
**Reversal:** trivial, deliberately not taken.

## D6 — `Finding` validator enforces provenance at construction time

**Alternative:** code review and convention.
**Chosen because:** "every claim has evidence" is the product's core promise; a runtime invariant makes
violating it impossible rather than discouraged.
**Cost:** analyzers must build `EvidenceRef`s even for trivial findings; a malformed finding raises,
which the pipeline must catch per-analyzer (it does).
**Reversal:** possible, but would silently weaken the guarantee.

## D7 — Ephemeral in-memory job store, deleted after client persistence

**Alternative:** SQLite, or keeping results server-side.
**Chosen because:** the requirement is explicit that the backend must not become a data store, and the
browser is the system of record.
**Cost:** results lost on restart; single process only; a 410 window if the client is slow.
**Reversal:** easy — `JobStore` is a protocol.

## D8 — Separate `scans` / `results` / `screenshots` object stores

**Alternative:** one record per scan.
**Chosen because:** the history list must open instantly without deserializing megabytes; screenshots
dominate size and need independent eviction under quota pressure.
**Cost:** writes and deletes must be transactional across stores (they are).
**Reversal:** cheap via a migration.

## D9 — Vendored, pinned axe-core

**Alternative:** load axe from a CDN at scan time, or use a wrapper package.
**Chosen because:** reproducible accessibility results require a byte-stable engine, and a CDN fetch
would add a per-scan network dependency plus a supply-chain hop.
**Cost:** manual version bumps, MPL-2.0 attribution to maintain.
**Reversal:** trivial.

## D10 — Hand-rolled ULID instead of a dependency

**Alternative:** `python-ulid`.
**Chosen because:** ~15 lines over `os.urandom` and `time.time_ns`; not worth a supply-chain surface.
**Cost:** ours to test (it is tested).
**Reversal:** trivial.

## D11 — `security.scoring` is a separate analyzer that consumes other findings

**Alternative:** each security analyzer contributes its own points.
**Chosen because:** the rule table stays in one auditable place, N/A arithmetic and band caps are
computed with full visibility of all observations, and rules can span analyzers (HSTS needs headers +
TLS).
**Cost:** requires `depends_on` ordering in the registry (topologically sorted, cycles fail at startup).
**Reversal:** cheap.

## D12 — `not_implemented` is a shipped, rendered state

**Alternative:** hide unbuilt sections.
**Chosen because:** phased delivery with an honest UI beats an empty panel, and it exercises the
degradation path from day one — the same code path that handles a real analyzer failure.
**Cost:** the UI must look deliberate while incomplete.
**Reversal:** disappears naturally as phases land.

## D13 — Python 3.12, not the machine default 3.14

**Chosen because:** Playwright does not advertise 3.14 support; 3.12 has wheels across the stack.
Enforced by `requires-python = ">=3.12,<3.13"` so it fails at install rather than at first scan.
**Reversal:** trivial once Playwright ships 3.14 wheels.

## D14 — Rejected: caching scans per URL

Tempting (scans are expensive), but it turns the backend into the persistent store the architecture
forbids and would serve stale claims about a site that has since changed. Recorded here so it is not
rediscovered as a "quick win".
