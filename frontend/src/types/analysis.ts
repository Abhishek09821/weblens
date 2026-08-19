/**
 * Domain contract.
 *
 * These schemas are the runtime gate at exactly two boundaries: API responses and IndexedDB
 * reads. Types are inferred from the schemas so there is one definition, not a type plus a
 * validator that drift apart.
 *
 * Structural keys (`status`, `findings`, `meta`) are strict, because a change there must break
 * loudly. Leaf payloads are lenient, because an additive backend change - a new `details` key, a
 * new payload field in a later phase - must not break a client that does not use it yet.
 *
 * Field names mirror the wire format (`snake_case`). See docs/blueprint/decisions.md D3.
 */
import { z } from 'zod';

export const SECTION_KEYS = [
  'design',
  'technology',
  'security',
  'performance',
  'accessibility',
  'seo',
  'architecture',
  'network',
] as const;

export const sectionKeySchema = z.enum(SECTION_KEYS);
export type SectionKey = z.infer<typeof sectionKeySchema>;

export const findingStatusSchema = z.enum([
  'verified',
  'inferred',
  'not_detected',
  'not_determinable',
  'unable_to_verify',
]);
export type FindingStatus = z.infer<typeof findingStatusSchema>;

export const sectionStatusSchema = z.enum([
  'complete',
  'partial',
  'unavailable',
  'not_implemented',
  'skipped',
]);
export type SectionStatus = z.infer<typeof sectionStatusSchema>;

export const scanStatusSchema = z.enum([
  'queued',
  'running',
  'completed',
  'completed_with_errors',
  'failed',
  'cancelled',
]);
export type ScanStatus = z.infer<typeof scanStatusSchema>;

export const stageStatusSchema = z.enum(['pending', 'running', 'completed', 'failed', 'skipped']);
export type StageStatus = z.infer<typeof stageStatusSchema>;

export const analyzerRunStatusSchema = z.enum([
  'completed',
  'failed',
  'skipped',
  'timeout',
  'not_implemented',
]);
export type AnalyzerRunStatus = z.infer<typeof analyzerRunStatusSchema>;

/**
 * Internal reasoning metadata carried for auditability in `analysis.json`. It is never rendered
 * as a claim qualifier; an eslint rule blocks reads of this field outside the report exporter.
 */
export const confidenceSchema = z.enum(['definitive', 'strong', 'moderate', 'weak']);
export type Confidence = z.infer<typeof confidenceSchema>;

export const evidenceRefSchema = z.object({
  kind: z.string(),
  source: z.string(),
  excerpt: z.string().nullish(),
  location: z.string().nullish(),
  detail: z.record(z.string(), z.unknown()).default({}),
});
export type EvidenceRef = z.infer<typeof evidenceRefSchema>;

export const findingSchema = z.object({
  id: z.string(),
  category: z.string(),
  name: z.string(),
  status: findingStatusSchema,
  detected: z.boolean().nullish(),
  value: z.union([z.string(), z.number(), z.boolean()]).nullish(),
  values: z.array(z.string()).default([]),
  unit: z.string().nullish(),
  confidence: confidenceSchema.nullish(),
  evidence: z.array(evidenceRefSchema).default([]),
  source: z.string(),
  details: z.record(z.string(), z.unknown()).default({}),
  limitations: z.array(z.string()).default([]),
  reason: z.string().nullish(),
});
export type Finding = z.infer<typeof findingSchema>;

export const interpretationSchema = z.object({
  id: z.string(),
  statement: z.string(),
  basis: z.array(z.string()),
  source: z.string(),
  caveat: z.string(),
});
export type Interpretation = z.infer<typeof interpretationSchema>;

export const analyzerRunSchema = z.object({
  id: z.string(),
  version: z.string(),
  status: analyzerRunStatusSchema,
  duration_ms: z.number().nullish(),
  error_code: z.string().nullish(),
  error_detail: z.string().nullish(),
  missing_evidence: z.array(z.string()).default([]),
});
export type AnalyzerRun = z.infer<typeof analyzerRunSchema>;

export const sectionMetaSchema = z.object({
  key: sectionKeySchema,
  status: sectionStatusSchema,
  analyzers: z.array(analyzerRunSchema).default([]),
  limitations: z.array(z.string()).default([]),
  unavailable_reason: z.string().nullish(),
});
export type SectionMeta = z.infer<typeof sectionMetaSchema>;

export const sectionSchema = z.object({
  meta: sectionMetaSchema,
  findings: z.array(findingSchema).default([]),
  interpretations: z.array(interpretationSchema).default([]),
  /** Typed per section as analyzers land; unknown until then rather than speculatively modelled. */
  data: z.unknown().nullish(),
});
export type Section = z.infer<typeof sectionSchema>;

// --- security score ---------------------------------------------------------------------

export const postureBandSchema = z.enum(['strong', 'good', 'moderate', 'limited', 'minimal']);
export type PostureBand = z.infer<typeof postureBandSchema>;

export const ruleOutcomeSchema = z.enum([
  'pass',
  'partial',
  'fail',
  'not_applicable',
  'unknown',
]);
export type RuleOutcome = z.infer<typeof ruleOutcomeSchema>;

export const securityRuleResultSchema = z.object({
  id: z.string(),
  title: z.string(),
  category: z.string(),
  outcome: ruleOutcomeSchema,
  weight: z.number(),
  awarded: z.number(),
  rationale: z.string(),
  evidence: z.array(evidenceRefSchema).default([]),
  recommendation: z.string().nullish(),
  reference: z.string().nullish(),
});
export type SecurityRuleResult = z.infer<typeof securityRuleResultSchema>;

export const securityScoreSchema = z.object({
  methodology_version: z.string(),
  points_awarded: z.number(),
  points_applicable: z.number(),
  percentage: z.number(),
  band: postureBandSchema,
  band_phrase: z.string(),
  label: z.string(),
  disclaimer: z.string(),
  rules: z.array(securityRuleResultSchema).default([]),
  excluded_rules: z
    .array(z.object({ id: z.string(), outcome: ruleOutcomeSchema, reason: z.string() }))
    .default([]),
  applied_caps: z
    .array(z.object({ rule_id: z.string(), cap: postureBandSchema, reason: z.string() }))
    .default([]),
});
export type SecurityScore = z.infer<typeof securityScoreSchema>;

// --- scan envelope ----------------------------------------------------------------------

export const viewportSchema = z.object({ width: z.number(), height: z.number() });

export const runContextSchema = z.object({
  browser_name: z.string().nullish(),
  browser_version: z.string().nullish(),
  user_agent: z.string(),
  viewport: viewportSchema,
  device_scale_factor: z.number(),
  wait_strategy: z.string(),
  settle_reached: z.boolean().nullish(),
  network_throttling: z.string(),
  cpu_throttling: z.string(),
  locale: z.string(),
  timezone: z.string(),
  collection_mode: z.string(),
});
export type RunContext = z.infer<typeof runContextSchema>;

export const stageRunSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: stageStatusSchema,
  started_at: z.string().nullish(),
  duration_ms: z.number().nullish(),
  error_code: z.string().nullish(),
  error_detail: z.string().nullish(),
  skip_reason: z.string().nullish(),
});
export type StageRun = z.infer<typeof stageRunSchema>;

export const scanOptionsSchema = z.object({
  include_screenshot: z.boolean(),
  include_full_page_screenshot: z.boolean(),
  viewport: viewportSchema,
  responsive_widths: z.array(z.number()),
  sections: z.array(sectionKeySchema).nullish(),
});
export type ScanOptions = z.infer<typeof scanOptionsSchema>;

export const scanMetadataSchema = z.object({
  scan_id: z.string(),
  status: scanStatusSchema,
  created_at: z.string(),
  started_at: z.string().nullish(),
  finished_at: z.string().nullish(),
  duration_ms: z.number().nullish(),
  engine_version: z.string(),
  schema_version: z.string(),
  options: scanOptionsSchema,
  run_context: runContextSchema.nullish(),
  stages: z.array(stageRunSchema).default([]),
});
export type ScanMetadata = z.infer<typeof scanMetadataSchema>;

export const robotsInfoSchema = z.object({
  url: z.string(),
  fetched: z.boolean(),
  status: z.number().nullish(),
  allowed: z.boolean().nullish(),
  matched_directive: z.string().nullish(),
  user_agent_group: z.string().nullish(),
  sitemaps: z.array(z.string()).default([]),
  error: z.string().nullish(),
});

export const targetInfoSchema = z.object({
  requested_url: z.string(),
  normalized_url: z.string(),
  final_url: z.string().nullish(),
  host: z.string(),
  port: z.number(),
  scheme: z.string(),
  resolved_ips: z.array(z.string()).default([]),
  redirect_chain: z
    .array(
      z.object({
        url: z.string(),
        status: z.number(),
        location: z.string().nullish(),
        scheme: z.string(),
      }),
    )
    .default([]),
  http_status: z.number().nullish(),
  document_title: z.string().nullish(),
  robots: robotsInfoSchema.nullish(),
});
export type TargetInfo = z.infer<typeof targetInfoSchema>;

export const scanErrorSchema = z.object({
  code: z.string(),
  scope: z.enum(['scan', 'stage', 'analyzer']),
  subject: z.string(),
  message: z.string(),
  detail: z.string().nullish(),
  occurred_at: z.string(),
});
export type ScanError = z.infer<typeof scanErrorSchema>;

export const screenshotRefSchema = z.object({
  label: z.string(),
  width: z.number(),
  height: z.number(),
  mime_type: z.string(),
  data_base64: z.string(),
});
export type ScreenshotRef = z.infer<typeof screenshotRefSchema>;

export const sectionSetSchema = z.object({
  design: sectionSchema,
  technology: sectionSchema,
  security: sectionSchema,
  performance: sectionSchema,
  accessibility: sectionSchema,
  seo: sectionSchema,
  architecture: sectionSchema,
  network: sectionSchema,
});
export type SectionSet = z.infer<typeof sectionSetSchema>;

export const analysisResultSchema = z.object({
  schema_version: z.string(),
  scan: scanMetadataSchema,
  target: targetInfoSchema,
  sections: sectionSetSchema,
  errors: z.array(scanErrorSchema).default([]),
  screenshots: z.array(screenshotRefSchema).default([]),
  limitations: z.array(z.string()).default([]),
});
export type AnalysisResult = z.infer<typeof analysisResultSchema>;

// --- job lifecycle ----------------------------------------------------------------------

export const problemDetailSchema = z.object({
  type: z.string(),
  title: z.string(),
  status: z.number(),
  detail: z.string().nullish(),
  code: z.string(),
  instance: z.string().nullish(),
  retryable: z.boolean().default(false),
});
export type ProblemDetail = z.infer<typeof problemDetailSchema>;

export const stageProgressSchema = z.object({
  current_stage: z.string().nullish(),
  current_stage_label: z.string().nullish(),
  completed_weight: z.number(),
  total_weight: z.number(),
  stages_completed: z.number(),
  stages_total: z.number(),
});
export type StageProgress = z.infer<typeof stageProgressSchema>;

export const scanJobStateSchema = z.object({
  scan_id: z.string(),
  status: scanStatusSchema,
  requested_url: z.string(),
  created_at: z.string(),
  started_at: z.string().nullish(),
  finished_at: z.string().nullish(),
  progress: stageProgressSchema,
  stages: z.array(stageRunSchema).default([]),
  problem: problemDetailSchema.nullish(),
});
export type ScanJobState = z.infer<typeof scanJobStateSchema>;

export const scanAcceptedSchema = z.object({
  scan_id: z.string(),
  status: scanStatusSchema,
  requested_url: z.string(),
  normalized_url: z.string(),
  created_at: z.string(),
  links: z.record(z.string(), z.string()),
});
export type ScanAccepted = z.infer<typeof scanAcceptedSchema>;

// --- capabilities and health -------------------------------------------------------------

export const analyzerCapabilitySchema = z.object({
  id: z.string(),
  section: sectionKeySchema,
  version: z.string(),
  description: z.string(),
  implemented: z.boolean(),
  requires: z.array(z.string()).default([]),
  depends_on: z.array(z.string()).default([]),
  planned_phase: z.number(),
});
export type AnalyzerCapability = z.infer<typeof analyzerCapabilitySchema>;

export const capabilitiesSchema = z.object({
  engine_version: z.string(),
  schema_version: z.string(),
  collection_mode: z.string(),
  sections: z.array(sectionKeySchema),
  analyzers: z.array(analyzerCapabilitySchema),
  stages: z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      weight: z.number(),
      implemented: z.boolean(),
      optional: z.boolean(),
    }),
  ),
  limits: z.record(z.string(), z.union([z.number(), z.boolean()])),
});
export type Capabilities = z.infer<typeof capabilitiesSchema>;

export const healthSchema = z.object({
  status: z.string(),
  engine_version: z.string(),
  schema_version: z.string(),
  uptime_seconds: z.number(),
  browser: z.object({
    available: z.boolean(),
    name: z.string().nullish(),
    version: z.string().nullish(),
    detail: z.string().nullish(),
  }),
  active_scans: z.number(),
});
export type Health = z.infer<typeof healthSchema>;

// --- SEO payload (the one section implemented in this build) ------------------------------

export const seoPayloadSchema = z.object({
  metadata: z
    .object({
      title: z.string().nullish(),
      title_length: z.number().nullish(),
      description: z.string().nullish(),
      description_length: z.number().nullish(),
      canonical: z.string().nullish(),
      robots_meta: z.string().nullish(),
      viewport_meta: z.string().nullish(),
      charset: z.string().nullish(),
      lang: z.string().nullish(),
      h1_texts: z.array(z.string()).default([]),
      open_graph: z
        .array(z.object({ key: z.string(), value: z.string().nullish() }))
        .default([]),
      twitter: z.array(z.object({ key: z.string(), value: z.string().nullish() })).default([]),
      hreflang: z
        .array(z.object({ hreflang: z.string(), href: z.string().nullish() }))
        .default([]),
      favicons: z.array(z.string()).default([]),
    })
    .nullish(),
  indexability: z.unknown().nullish(),
  structured_data: z
    .array(
      z.object({
        format: z.string(),
        types: z.array(z.string()).default([]),
        valid: z.boolean(),
        parse_error: z.string().nullish(),
        raw_length: z.number().nullish(),
      }),
    )
    .default([]),
});
export type SeoPayload = z.infer<typeof seoPayloadSchema>;
