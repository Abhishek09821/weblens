# 10. Report generation architecture

## Decision: reports are rendered on the client

Rendering happens in `frontend/src/features/reports/`, in TypeScript, from the `AnalysisResult`
stored in IndexedDB.

Rationale:

- The scan result must remain fully usable after a browser restart **with the backend stopped**. A
  server-side renderer would make downloads depend on a live backend and on the backend still holding
  a result it is explicitly not allowed to retain.
- One implementation, not two. A Python renderer plus a TS renderer would be duplicate logic (an
  explicit quality constraint), and the two would drift.
- Reports are a pure function of the result. There is no server-only input, so there is no reason for
  the work to be server-side.

Tradeoff accepted: no `curl`-able report endpoint in V1. If that is ever needed, the renderer is a
pure module and can be ported or run in a Node script against `analysis.json`; the report contract
(`ReportBundle`) is defined so that a future server-side implementation produces byte-identical files.

## Structure

```
features/reports/
├── generate.ts             # orchestration: result → ReportBundle
├── bundle.ts               # zip assembly (fflate), file naming, manifest
├── download.ts             # Blob + anchor download, object URL lifecycle
├── markdown/
│   ├── kit.ts              # heading/table/list/code/kv builders, escaping
│   ├── shared.ts           # front-matter, scan metadata block, limitations block, footer
│   └── renderers/
│       ├── design.ts  techstack.ts  security.ts  performance.ts
│       ├── accessibility.ts  seo.ts  architecture.ts
│       └── index.ts        # SectionKey → renderer registry
└── json.ts                 # analysis.json serialization (stable key order)
```

```ts
export interface ReportFile { path: string; contents: string | Uint8Array; bytes: number; }
export interface ReportBundle { files: ReportFile[]; manifest: ReportManifest; }

export type SectionRenderer = (ctx: RenderContext) => string;
export interface RenderContext {
  result: AnalysisResult;
  section: Section<unknown>;
  options: { includeEvidence: boolean; maxEvidencePerFinding: number };
}
```

Registry-driven: adding a section means adding one renderer and one registry entry.

## Output files

| File | Source | Notes |
|------|--------|-------|
| `design.md` | `sections.design` | facts tables, then a clearly fenced Interpretation block |
| `techstack.md` | `sections.technology` | products grouped by category, version or "not determinable" |
| `security.md` | `sections.security` | posture score, full rule table, methodology, disclaimer |
| `performance.md` | `sections.performance` | metrics with units + run context caveat |
| `accessibility.md` | `sections.accessibility` | violations by impact + structural observations + coverage note |
| `seo.md` | `sections.seo` | metadata, indexability, structured data |
| `architecture.md` | `sections.architecture` + `sections.network` | runtime/rendering/platform, then network detail |
| `analysis.json` | whole result | the machine-readable source of truth |
| `README.md` | manifest | what is in the bundle, how it was produced, how to read statuses |
| `complete-report.zip` | all of the above | plus `screenshots/*.png` when present |

`architecture.md` intentionally absorbs the network section rather than emitting a ninth file: the
requirement lists seven markdown reports, and network observations are the evidence base for the
architecture conclusions, so they belong in the same document under their own heading.

## Every report includes

1. **Front matter** — target URL (requested + final), scan id, scan timestamps (ISO-8601 UTC + local),
   engine version, schema version, section status, generator version.
2. **Run context** — browser name/version, viewport, wait strategy, throttling. Without this,
   performance and design numbers are not interpretable.
3. **Findings** — grouped by category. Each row: name, status, value (+ unit), and reason for negative
   statuses. Status is spelled out in words; `confidence` is never printed as a claim qualifier.
4. **Evidence** — for asserted findings, a collapsed detail list: `kind`, `source`, `location`,
   excerpt in a fenced block. Toggleable via `includeEvidence` (default on).
5. **Limitations** — section limitations plus scan-wide limitations, verbatim from the result.
6. **Footer** — the standing disclaimer that this is a passive, single-run, external observation.

Unavailable sections still produce their file, containing the status, the `unavailable_reason`, the
analyzer runs that failed, and nothing else. An empty-but-explained file is far more useful than a
missing one, and it makes partial scans self-documenting.

## Determinism and safety

- Stable ordering everywhere: sections in canonical order, findings by `(category, id)`, rules by
  declared weight then id. Two runs over the same result produce byte-identical output, which is what
  makes report snapshot tests meaningful.
- `analysis.json` is serialized with sorted keys and a trailing newline.
- Markdown escaping: pipes/backticks/newlines in evidence excerpts are escaped or fenced so a hostile
  page cannot break out of a table cell or inject a fake heading into the report.
- No secrets: `Set-Cookie` values are reduced to attribute observations (name + flags, never the
  value), `Authorization`-class request headers are never captured, and query strings are redacted for
  known credential-ish parameter names (`token`, `key`, `signature`, `password`, `access_token`) at
  collection time, so redaction is applied before evidence ever exists.
- Filenames are fixed literals; the zip never derives a path from target-controlled input.

## Download UX

- Per-section download (one `.md`) from each section header.
- "Download all" produces `complete-report.zip` via `fflate.zipSync` off the main thread when the
  result is large (Web Worker in a later phase; V1 uses the async `zip` callback API).
- Suggested filename: `weblens-<host>-<yyyymmdd-hhmmss>.zip`, host slugified to `[a-z0-9.-]`.
- `URL.revokeObjectURL` is called after the download click in every path, including error paths.
