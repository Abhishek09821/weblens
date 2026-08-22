/**
 * Focused overview derived from structured V2 results.
 *
 * Every claim here traces back to a finding or section metadata. AI hypotheses are deliberately
 * excluded from the overview so they cannot be mistaken for detected technology.
 */
import {
  securityPayloadSchema,
  trafficPayloadSchema,
  type AnalysisResult,
  type Finding,
  type FindingStatus,
} from '@/types/analysis';

export interface OverviewData {
  target: {
    host: string;
    url: string;
    httpStatus: number | null;
    scanStatus: AnalysisResult['scan']['status'];
  };
  technology: {
    items: Array<{ name: string; status: FindingStatus }>;
    rendering: { value: string; status: FindingStatus } | null;
    unavailable: boolean;
  };
  design: {
    fonts: string[];
    colorsObserved: number | null;
    observations: string[];
    unavailable: boolean;
  };
  security: {
    percentage: number | null;
    bandPhrase: string | null;
    disclaimer: string | null;
  };
  traffic: {
    providerName: string | null;
    providerAvailable: boolean;
    estimates: Array<{ name: string; value: string; status: FindingStatus }>;
    analyticsServices: string[];
    unavailableReason: string | null;
  };
  evidence: {
    verified: number;
    stronglyInferred: number;
    inferred: number;
    aiInferred: number;
    unknown: number;
    analyzersCompleted: number;
    analyzersTotal: number;
    limitationCount: number;
    errorCount: number;
  };
}

const OVERVIEW_TECH_SOURCES = [
  'technology.framework',
  'technology.stack',
  'technology.styling',
  'technology.language',
  'architecture.platform',
] as const;

export function buildOverview(result: AnalysisResult): OverviewData {
  return {
    target: {
      host: result.target.host,
      url: result.target.final_url ?? result.target.normalized_url,
      httpStatus: result.target.http_status ?? null,
      scanStatus: result.scan.status,
    },
    technology: buildTechnologySummary(result),
    design: buildDesignSummary(result),
    security: buildSecuritySummary(result),
    traffic: buildTrafficSummary(result),
    evidence: buildEvidenceSummary(result),
  };
}

function buildTechnologySummary(result: AnalysisResult): OverviewData['technology'] {
  const section = result.sections.technology;
  const items = deduplicateFindings(
    section.findings.filter(
      (finding) =>
        finding.detected === true &&
        finding.status !== 'ai_inferred' &&
        isAssertedStatus(finding.status) &&
        OVERVIEW_TECH_SOURCES.some((source) => finding.source === source),
    ),
  )
    .slice(0, 8)
    .map((finding) => ({ name: technologyName(finding), status: finding.status }));

  const renderingFinding = section.findings.find(
    (finding) =>
      finding.id === 'architecture.rendering:rendering-strategy' &&
      isAssertedStatus(finding.status) &&
      finding.value !== null &&
      finding.value !== undefined,
  );

  return {
    items,
    rendering: renderingFinding
      ? {
          value: humanize(String(renderingFinding.value)),
          status: renderingFinding.status,
        }
      : null,
    unavailable: section.meta.status === 'unavailable' || section.meta.status === 'not_implemented',
  };
}

function buildDesignSummary(result: AnalysisResult): OverviewData['design'] {
  const section = result.sections.design;
  const fontFinding = findById(section.findings, 'design.typography:loaded-fonts');
  const colorFinding = findById(section.findings, 'design.color:background-colors');
  const observations: string[] = [];

  const layoutFinding = findById(section.findings, 'design.layout:display-types');
  if (layoutFinding?.values.some((value) => value === 'flex' || value === 'grid')) {
    observations.push('Flex/grid layout');
  }
  if ((findById(section.findings, 'design.layout:breakpoints')?.values.length ?? 0) > 0) {
    observations.push('Responsive breakpoints observed');
  }
  if ((findById(section.findings, 'design.layout:gap-values')?.values.length ?? 0) > 0) {
    observations.push('Reusable spacing values');
  }
  if ((findById(section.findings, 'design.motion:transitions')?.values.length ?? 0) > 0) {
    observations.push('CSS transitions observed');
  }

  return {
    fonts: fontFinding?.values.slice(0, 4) ?? [],
    colorsObserved: typeof colorFinding?.value === 'number' ? colorFinding.value : null,
    observations,
    unavailable: section.meta.status === 'unavailable' || section.meta.status === 'not_implemented',
  };
}

function buildSecuritySummary(result: AnalysisResult): OverviewData['security'] {
  const parsed = securityPayloadSchema.safeParse(result.sections.security.data);
  const score = parsed.success ? parsed.data.score : null;
  return {
    percentage: score?.percentage ?? null,
    bandPhrase: score?.band_phrase ?? null,
    disclaimer: score?.disclaimer ?? null,
  };
}

function buildTrafficSummary(result: AnalysisResult): OverviewData['traffic'] {
  const section = result.sections.traffic;
  const parsed = trafficPayloadSchema.safeParse(section.data);
  const providerName = parsed.success ? (parsed.data.provider_name ?? null) : null;
  const providerAvailable = parsed.success ? parsed.data.provider_available : false;
  const popularity = section.findings.filter((finding) => finding.category === 'popularity');
  const estimates = popularity
    .filter(
      (finding) =>
        isAssertedStatus(finding.status) &&
        (finding.value !== null || finding.values.length > 0),
    )
    .map((finding) => ({
      name: finding.name,
      value: finding.value === null || finding.value === undefined
        ? finding.values.join(', ')
        : String(finding.value),
      status: finding.status,
    }));

  const analyticsServices = section.findings
    .filter((finding) => finding.category === 'analytics' && finding.detected === true)
    .flatMap((finding) => (finding.values.length > 0 ? finding.values : [String(finding.value ?? finding.name)]));
  const unavailableFinding = popularity.find(
    (finding) => finding.status === 'unable_to_verify' || finding.status === 'not_determinable',
  );

  return {
    providerName,
    providerAvailable,
    estimates,
    analyticsServices: [...new Set(analyticsServices)].slice(0, 6),
    unavailableReason:
      estimates.length > 0
        ? null
        : (unavailableFinding?.reason ?? section.meta.unavailable_reason ?? 'No public traffic estimate was available.'),
  };
}

function buildEvidenceSummary(result: AnalysisResult): OverviewData['evidence'] {
  const sections = Object.values(result.sections);
  const findings = sections.flatMap((section) => section.findings);
  const analyzers = sections.flatMap((section) => section.meta.analyzers);
  const count = (status: FindingStatus) => findings.filter((finding) => finding.status === status).length;

  return {
    verified: count('verified'),
    stronglyInferred: count('strongly_inferred'),
    inferred: count('inferred'),
    aiInferred: count('ai_inferred'),
    unknown: count('not_detected') + count('not_determinable') + count('unable_to_verify'),
    analyzersCompleted: analyzers.filter((analyzer) => analyzer.status === 'completed').length,
    analyzersTotal: analyzers.length,
    limitationCount:
      result.limitations.length +
      sections.reduce((total, section) => total + section.meta.limitations.length, 0),
    errorCount: result.errors.length,
  };
}

function technologyName(finding: Finding): string {
  if (
    typeof finding.value === 'string' &&
    ['Hosting platform', 'Server-side technology'].includes(finding.name)
  ) {
    return finding.value;
  }
  return finding.name.replace('Platform: ', '');
}

function deduplicateFindings(findings: Finding[]): Finding[] {
  const seen = new Set<string>();
  return findings.filter((finding) => {
    const name = technologyName(finding).toLowerCase();
    if (seen.has(name)) return false;
    seen.add(name);
    return true;
  });
}

function isAssertedStatus(status: FindingStatus): boolean {
  return status === 'verified' || status === 'strongly_inferred' || status === 'inferred';
}

function findById(findings: Finding[], id: string): Finding | undefined {
  return findings.find((finding) => finding.id === id);
}

function humanize(value: string): string {
  return value.replace(/[_-]+/g, ' ');
}
