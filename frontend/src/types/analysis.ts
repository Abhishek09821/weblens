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

export const SECTION_KEYS = ['design', 'technology', 'security', 'traffic'] as const;

export const sectionKeySchema = z.enum(SECTION_KEYS);
export type SectionKey = z.infer<typeof sectionKeySchema>;

export const findingStatusSchema = z.enum([
  'verified',
  'strongly_inferred',
  'inferred',
  'ai_inferred',
  'not_detected',
  'not_determinable',
  'unable_to_verify',
]);
export type FindingStatus = z.infer<typeof findingStatusSchema>;

export const sectionStatusSchema = z.enum([
  'complete',
  'partial',
  'insufficient_evidence',
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

export const designPayloadSchema = z.object({
  coverage: z
    .object({
      cap_hit: z.boolean(),
      elements_sampled: z.number(),
      elements_total: z.number().nullish(),
    })
    .nullish(),
  axe: z.unknown().nullish(),
});
export type DesignPayload = z.infer<typeof designPayloadSchema>;

export const securityPayloadSchema = z.object({
  score: securityScoreSchema.nullish(),
  headers: z
    .array(
      z.object({
        name: z.string(),
        present: z.boolean(),
        value: z.string().nullish(),
      }),
    )
    .default([]),
});
export type SecurityPayload = z.infer<typeof securityPayloadSchema>;

export const trafficPayloadSchema = z.object({
  provider_name: z.string().nullish(),
  provider_available: z.boolean().default(false),
});
export type TrafficPayload = z.infer<typeof trafficPayloadSchema>;

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
  traffic: sectionSchema,
});
export type SectionSet = z.infer<typeof sectionSetSchema>;

// --- evidence quality gate -------------------------------------------------------------

export const evidenceQualitySchema = z.enum(['high', 'medium', 'low', 'failed']);
export type EvidenceQuality = z.infer<typeof evidenceQualitySchema>;

export const sectionQualitySchema = z.object({
  section: sectionKeySchema,
  quality: evidenceQualitySchema,
  score: z.number(),
  analyzers_completed: z.number(),
  analyzers_total: z.number(),
  findings_verified: z.number(),
  findings_inferred: z.number(),
  findings_negative: z.number(),
  ai_fallback_recommended: z.boolean(),
  reason: z.string(),
});
export type SectionQuality = z.infer<typeof sectionQualitySchema>;

export const scanQualitySchema = z.object({
  overall: evidenceQualitySchema,
  overall_score: z.number(),
  sections: z.record(sectionKeySchema, sectionQualitySchema),
  ai_fallback_available: z.boolean(),
  ai_fallback_sections: z.array(sectionKeySchema).default([]),
});
export type ScanQuality = z.infer<typeof scanQualitySchema>;

// --- analysis result -------------------------------------------------------------------

export const analysisResultSchema = z.object({
  schema_version: z.literal('2.0'),
  scan: scanMetadataSchema,
  target: targetInfoSchema,
  sections: sectionSetSchema,
  quality: scanQualitySchema.nullish(),
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
  research_available: z.boolean(),
  inference_available: z.boolean(),
  traffic_provider_available: z.boolean(),
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

// --- AI intelligence fallback -----------------------------------------------------------

export interface IntelligenceStatus {
  available: boolean;
  research_available: boolean;
  inference_available: boolean;
  reason: string | null;
}

export interface IntelligenceResponse {
  scan_id: string;
  mode: string;
  sections_enhanced: SectionKey[];
  research_performed: boolean;
  research_available: boolean;
  findings_added: number;
  quality_before: ScanQuality | null;
  quality_after: ScanQuality | null;
  limitations: string[];
}

// --- Verdict engine types ---------------------------------------------------------------

export const VERDICT_CATEGORIES = [
  'verified',
  'strongly_supported',
  'likely',
  'possible',
  'not_detected',
  'not_publicly_determinable',
  'unable_to_verify',
] as const;

export type VerdictCategory = (typeof VERDICT_CATEGORIES)[number];

/**
 * Maps verdict category to a human-readable label for reports.
 */
export function verdictLabel(category: VerdictCategory): string {
  const labels: Record<VerdictCategory, string> = {
    verified: 'Verified',
    strongly_supported: 'Strongly Supported',
    likely: 'Likely',
    possible: 'Possible',
    not_detected: 'Not Detected',
    not_publicly_determinable: 'Not Publicly Determinable',
    unable_to_verify: 'Unable to Verify',
  };
  return labels[category];
}

/**
 * Maps a FindingStatus to the closest verdict category for display purposes.
 */
export function findingStatusToVerdict(status: FindingStatus): VerdictCategory {
  switch (status) {
    case 'verified':
      return 'verified';
    case 'strongly_inferred':
      return 'strongly_supported';
    case 'inferred':
      return 'likely';
    case 'ai_inferred':
      return 'likely';
    case 'not_detected':
      return 'not_detected';
    case 'not_determinable':
      return 'not_publicly_determinable';
    case 'unable_to_verify':
      return 'unable_to_verify';
  }
}
