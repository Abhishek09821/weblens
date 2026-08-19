# WebLens Implementation Blueprint

WebLens is a **Website Technical Intelligence Analyzer**. A user submits a publicly reachable URL;
WebLens collects observable evidence from that site with a real browser and HTTP/TLS probes, runs
deterministic analyzers over that evidence, and renders a technical report.

## Non-negotiable design axioms

These constrain every document that follows. If a later decision conflicts with one of these, the
axiom wins.

| # | Axiom | Enforced by |
|---|-------|-------------|
| A1 | Detection is never performed by an AI model | `analyzers/` contain pure functions over evidence; no network/LLM access in the analyzer layer |
| A2 | Every asserted fact carries provenance | `Finding.evidence: list[EvidenceRef]` is non-optional for `verified` / `inferred` findings; enforced by a model validator |
| A3 | Unknown is a first-class result | `FindingStatus` includes `not_detected`, `not_determinable`, `unable_to_verify`; sections can be `unavailable` |
| A4 | Only security is scored | `SecurityScore` is the single score type in the domain model. No other section may define one |
| A5 | Confidence is internal metadata | `Finding.confidence` never drives UI copy; the UI renders `Finding.status` |
| A6 | Passive analysis only | The collection layer performs navigation + read-only probes. No fuzzing, no auth attempts, no payloads |
| A7 | One analyzer failing must not fail the scan | Analyzers run isolated; failures degrade a section, not the result |
| A8 | The browser is the source of truth for runtime facts | Static-HTML-only conclusions are marked as such when a browser observation was unavailable |
| A9 | AI output is presentation, never a fact source | The AI layer receives findings and may only reference existing finding IDs; ungrounded claims are dropped |
| A10 | No per-site special cases | No hostname branching anywhere in `analyzers/` or `collection/`; signature data is generic and evidence-keyed |

## Deliverable map

| # | Deliverable | Document |
|---|-------------|----------|
| 1 | Repository structure | [01-repository-structure.md](01-repository-structure.md) |
| 2 | Frontend architecture | [02-frontend-architecture.md](02-frontend-architecture.md) |
| 3 | Backend architecture | [03-backend-architecture.md](03-backend-architecture.md) |
| 4 | Scanner architecture | [04-scanner-architecture.md](04-scanner-architecture.md) |
| 5 | Analyzer module design | [05-analyzer-module-design.md](05-analyzer-module-design.md) |
| 6 | API contract design | [06-api-contract.md](06-api-contract.md) |
| 7 | Pydantic models | [07-pydantic-models.md](07-pydantic-models.md) |
| 8 | TypeScript data models | [08-typescript-models.md](08-typescript-models.md) |
| 9 | IndexedDB storage model | [09-indexeddb-storage-model.md](09-indexeddb-storage-model.md) |
| 10 | Report generation architecture | [10-report-generation.md](10-report-generation.md) |
| 11 | Security scoring methodology | [11-security-scoring-methodology.md](11-security-scoring-methodology.md) |
| 12 | Testing strategy | [12-testing-strategy.md](12-testing-strategy.md) |
| 13 | Development phases | [13-development-phases.md](13-development-phases.md) |
| 14 | Dependency list | [14-dependencies.md](14-dependencies.md) |
| 15 | Technical risks and limitations | [15-risks-and-limitations.md](15-risks-and-limitations.md) |

Key decisions with tradeoffs are recorded in [decisions.md](decisions.md).

## The pipeline in one line

```
URL → validate/guard → collect (HTTP + TLS + DNS + robots + Playwright) → RawEvidence
    → deterministic analyzers → AnalysisResult → API → IndexedDB → dashboard + reports
                                             ↘ (optional, labelled) AI explanation layer
```

## Vocabulary

- **Evidence** — a raw observation captured from the target (a header value, a script URL, a computed
  style, a performance entry). Evidence is collected once, never re-fetched by analyzers.
- **Finding** — an analyzer's structured conclusion about one property, linked to the evidence that
  supports it.
- **Interpretation** — a subjective/derived statement (e.g. "dark SaaS-like visual language") that
  explicitly cites the findings it is based on and is rendered separately from facts.
- **Section** — one report area (design, technology, security, performance, accessibility, seo,
  architecture, network) with its own status and limitations.
- **Scan** — one execution of the pipeline against one URL, producing one `AnalysisResult`.
