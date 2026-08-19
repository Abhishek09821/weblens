# 8. TypeScript data models (frontend)

Two type sources, each with a distinct job. Both are checked against each other in CI.

| Source | File | Role |
|--------|------|------|
| Generated from OpenAPI | `src/types/api.generated.ts` | mechanical mirror of the backend schema; proves the hand-authored types have not drifted |
| Hand-authored + zod | `src/types/analysis.ts` | the types the app actually programs against, plus runtime validation at the network boundary |

Why both: generated types alone give no runtime safety (a backend change or a corrupted IndexedDB
record would surface as `undefined` deep in a component), and hand-authored types alone drift. The
zod schema is the single runtime gate; `api.generated.ts` exists so a drift test can fail loudly.

## Core types (`src/types/analysis.ts`)

```ts
export const SECTION_KEYS = ['design','technology','security','performance',
  'accessibility','seo','architecture','network'] as const;
export type SectionKey = (typeof SECTION_KEYS)[number];

export type FindingStatus =
  | 'verified' | 'inferred' | 'not_detected' | 'not_determinable' | 'unable_to_verify';

export type SectionStatus =
  | 'complete' | 'partial' | 'unavailable' | 'not_implemented' | 'skipped';

export type ScanStatus =
  | 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled';

/** Internal reasoning metadata. Never rendered as a claim qualifier (axiom A5). */
export type Confidence = 'definitive' | 'strong' | 'moderate' | 'weak';

export interface EvidenceRef {
  kind: EvidenceKind;
  source: string;
  excerpt: string | null;
  location: string | null;
  detail: Record<string, unknown>;
}

export interface Finding {
  id: string;
  category: string;
  name: string;
  status: FindingStatus;
  detected: boolean | null;
  value: string | number | boolean | null;
  values: string[];
  unit: string | null;
  confidence: Confidence | null;
  evidence: EvidenceRef[];
  source: string;
  details: Record<string, unknown>;
  limitations: string[];
  reason: string | null;
}

export interface Interpretation {
  id: string; statement: string; basis: string[]; source: string; caveat: string;
}

export interface Section<TPayload = unknown> {
  meta: SectionMeta;
  findings: Finding[];
  interpretations: Interpretation[];
  data: TPayload | null;
}

export interface AnalysisResult {
  schema_version: '1.0';
  scan: ScanMetadata;
  target: TargetInfo;
  sections: {
    design: Section<DesignPayload>;
    technology: Section<TechnologyPayload>;
    security: Section<SecurityPayload>;
    performance: Section<PerformancePayload>;
    accessibility: Section<AccessibilityPayload>;
    seo: Section<SeoPayload>;
    architecture: Section<ArchitecturePayload>;
    network: Section<NetworkPayload>;
  };
  errors: ScanError[];
  screenshots: ScreenshotRef[];
  limitations: string[];
}
```

Naming mirrors the wire format (`snake_case`) exactly — no mapping layer, per doc 6.

## Runtime validation strategy

```ts
export const analysisResultSchema = z.object({ /* … */ });
export type AnalysisResultParsed = z.infer<typeof analysisResultSchema>;
```

Validation happens at exactly two boundaries:

1. **API → app**: `parseResult(json)` in `lib/api/parse.ts`. A failure produces a typed
   `ContractError` surfaced as "the analyzer returned an unexpected shape", never a blank screen.
2. **IndexedDB → app**: the same schema on read. Records written by an older `schema_version` are run
   through migrations first (doc 9); anything still invalid is quarantined, not silently rendered.

Payload sub-objects are validated with `.passthrough()`-style leniency at the leaves
(`z.record(z.unknown())` for `details`) so an additive backend change (a new `details` key) is
forward-compatible, while structural keys (`status`, `findings`, `meta`) are strict. Additive changes
must not break a client; structural changes must.

## Display helpers, not display types

The UI does not define parallel view-models. It uses small pure helpers over the domain types:

```ts
statusLabel(status: FindingStatus): string          // 'verified' → 'Verified'
statusTone(status: FindingStatus): 'positive' | 'neutral' | 'muted' | 'warning'
isAsserted(f: Finding): boolean                      // verified | inferred
sectionIsRenderable(s: Section): boolean             // complete | partial
formatValue(f: Finding): string                      // applies f.unit, never invents precision
```

`statusTone` deliberately maps `not_detected`, `not_determinable`, and `unable_to_verify` to *neutral
or muted* tones, never to red. Absence of a signal is not a failure, and colouring it as one would be
the UI lying on the analyzer's behalf. `security` rule outcomes are the only place where a
pass/fail colour scale is used, because there the judgement is explicit and documented.

## Scan lifecycle types (`features/scan/types.ts`)

```ts
export type ScanPhase =
  | { kind: 'idle' }
  | { kind: 'invalid'; message: string }
  | { kind: 'submitting'; url: string }
  | { kind: 'running'; scanId: string; job: ScanJobState }
  | { kind: 'persisting'; scanId: string }
  | { kind: 'ready'; scanId: string; hasErrors: boolean }
  | { kind: 'failed'; problem: ProblemDetail };
```

A discriminated union rather than booleans: it makes "submitting and failed" unrepresentable and lets
the progress component exhaustively `switch` with no default branch.

## Local record types (`lib/db/types.ts`)

```ts
export interface ScanRecord {          // small: powers the history list without loading results
  id: string;
  requested_url: string;
  normalized_url: string;
  final_url: string | null;
  host: string;
  status: ScanStatus;
  created_at: string;                  // ISO-8601, from the backend
  saved_at: string;                    // ISO-8601, client clock
  duration_ms: number | null;
  engine_version: string;
  schema_version: string;
  section_statuses: Record<SectionKey, SectionStatus>;
  security_percentage: number | null;  // denormalized for the list, nullable by design
  error_count: number;
  has_screenshot: boolean;
  result_bytes: number;
}

export interface ResultRecord { scan_id: string; schema_version: string; result: AnalysisResult; }
export interface ScreenshotRecord { scan_id: string; items: { label: string; blob: Blob; width: number; height: number }[]; }
```

`ScanRecord` is a projection, not a duplicate: it holds only what the library list renders, so opening
`/` never deserializes megabytes of results. `security_percentage` is `null` when the security section
is not `complete` — the list shows "—", not a zero.
