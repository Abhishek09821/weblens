/**
 * Executive overview derived from structured analysis results.
 *
 * Every claim here traces back to a finding. Nothing is invented.
 * This layer transforms raw findings into user-facing summaries.
 */
import type { AnalysisResult, Finding } from '@/types/analysis';
import { securityScoreSchema } from '@/types/analysis';

export interface OverviewData {
  target: { host: string; url: string; httpStatus: number | null };
  technology: TechSummary;
  rendering: RenderingSummary;
  design: DesignSummary;
  security: SecuritySummary;
  performance: PerformanceSummary;
  accessibility: AccessibilitySummary;
  seo: SeoSummary;
  infrastructure: InfraSummary;
}

export interface TechSummary {
  detected: string[];
  status: 'available' | 'none_detected' | 'unavailable';
}

export interface RenderingSummary {
  strategy: string | null;
  certainty: string | null;
}

export interface DesignSummary {
  fonts: string[];
  colorCount: number | null;
  hasResponsive: boolean;
  observations: string[];
}

export interface SecuritySummary {
  percentage: number | null;
  band: string | null;
  bandPhrase: string | null;
  strongControls: string[];
  missingControls: string[];
}

export interface PerformanceSummary {
  ttfb: number | null;
  fcp: number | null;
  lcp: number | null;
  transferBytes: number | null;
  requestCount: number | null;
}

export interface AccessibilitySummary {
  issues: string[];
  violationCount: number | null;
}

export interface SeoSummary {
  title: string | null;
  hasDescription: boolean;
  hasCanonical: boolean;
  hasOpenGraph: boolean;
  hasStructuredData: boolean;
}

export interface InfraSummary {
  platforms: string[];
  cdn: string[];
  server: string[];
}

export function buildOverview(result: AnalysisResult): OverviewData {
  return {
    target: {
      host: result.target.host,
      url: result.target.final_url ?? result.target.normalized_url,
      httpStatus: result.target.http_status ?? null,
    },
    technology: extractTechSummary(result),
    rendering: extractRenderingSummary(result),
    design: extractDesignSummary(result),
    security: extractSecuritySummary(result),
    performance: extractPerformanceSummary(result),
    accessibility: extractAccessibilitySummary(result),
    seo: extractSeoSummary(result),
    infrastructure: extractInfraSummary(result),
  };
}

function extractTechSummary(result: AnalysisResult): TechSummary {
  const section = result.sections.technology;
  if (section.meta.status === 'unavailable' || section.meta.status === 'not_implemented') {
    return { detected: [], status: 'unavailable' };
  }
  const detected = section.findings
    .filter((f) => f.status === 'verified' || f.status === 'inferred')
    .map((f) => f.name)
    .filter((name) => !name.includes('Server-side technology'));
  return { detected, status: detected.length > 0 ? 'available' : 'none_detected' };
}

function extractRenderingSummary(result: AnalysisResult): RenderingSummary {
  const finding = findById(result.sections.architecture.findings, 'architecture.rendering:rendering-strategy');
  if (!finding || !finding.value) return { strategy: null, certainty: null };
  const strategy = String(finding.value).replace(/_/g, ' ');
  const certainty = finding.status === 'verified' ? 'Verified' : 'Inferred';
  return { strategy, certainty };
}

function extractDesignSummary(result: AnalysisResult): DesignSummary {
  const section = result.sections.design;
  const fonts: string[] = [];
  const observations: string[] = [];

  const fontFinding = findById(section.findings, 'design.typography:loaded-fonts');
  if (fontFinding?.values) fonts.push(...fontFinding.values.slice(0, 4));

  const bgFinding = findById(section.findings, 'design.color:background-colors');
  const colorCount = typeof bgFinding?.value === 'number' ? bgFinding.value : null;

  // Check responsive
  const breakpoints = findById(section.findings, 'design.layout:breakpoints');
  const hasResponsive = breakpoints != null && (breakpoints.value as number) > 0;

  // Build observations
  const displayTypes = findById(section.findings, 'design.layout:display-types');
  if (displayTypes?.values?.includes('flex') || displayTypes?.values?.includes('grid')) {
    observations.push('Modern layout (flex/grid)');
  }
  if (hasResponsive) observations.push('Responsive layout');
  const radii = findById(section.findings, 'design.layout:border-radius');
  if (radii && (radii.value as number) > 0) observations.push('Rounded controls');
  const shadows = findById(section.findings, 'design.layout:box-shadows');
  if (shadows && (shadows.value as number) > 0) observations.push('Subtle shadows');
  const transitions = findById(section.findings, 'design.motion:transitions');
  if (transitions && (transitions.value as number) > 0) observations.push('CSS transitions');

  return { fonts, colorCount, hasResponsive, observations };
}

function extractSecuritySummary(result: AnalysisResult): SecuritySummary {
  const section = result.sections.security;
  const raw = section.data && typeof section.data === 'object'
    ? (section.data as { score?: unknown }).score : undefined;
  const parsed = securityScoreSchema.safeParse(raw);

  if (!parsed.success) {
    return { percentage: null, band: null, bandPhrase: null, strongControls: [], missingControls: [] };
  }

  const score = parsed.data;
  const strong = score.rules.filter((r) => r.outcome === 'pass').map((r) => r.title);
  const missing = score.rules.filter((r) => r.outcome === 'fail').map((r) => r.title);

  return {
    percentage: score.percentage,
    band: score.band,
    bandPhrase: score.band_phrase,
    strongControls: strong,
    missingControls: missing,
  };
}

function extractPerformanceSummary(result: AnalysisResult): PerformanceSummary {
  const section = result.sections.performance;
  return {
    ttfb: findNumericValue(section.findings, 'performance.timings:ttfb'),
    fcp: findNumericValue(section.findings, 'performance.timings:fcp'),
    lcp: findNumericValue(section.findings, 'performance.timings:lcp'),
    transferBytes: findNumericValue(section.findings, 'performance.resources:transfer-size'),
    requestCount: findNumericValue(section.findings, 'performance.resources:request-count'),
  };
}

function extractAccessibilitySummary(result: AnalysisResult): AccessibilitySummary {
  const section = result.sections.accessibility;
  const issues: string[] = [];

  const missingAlt = findById(section.findings, 'accessibility.structure:images-missing-alt');
  if (missingAlt && typeof missingAlt.value === 'number' && missingAlt.value > 0) {
    issues.push(`${missingAlt.value} images without alt text`);
  }

  const formLabels = findById(section.findings, 'accessibility.structure:form-labels');
  if (formLabels && typeof formLabels.value === 'number' && formLabels.value > 0) {
    issues.push(`${formLabels.value} form inputs without labels`);
  }

  const headings = findById(section.findings, 'accessibility.structure:heading-hierarchy');
  if (headings && headings.values && headings.values.length > 0) {
    issues.push('Heading hierarchy issues detected');
  }

  const violationCount = findNumericValue(section.findings, 'accessibility.axe:violation-count');

  return { issues, violationCount };
}

function extractSeoSummary(result: AnalysisResult): SeoSummary {
  const section = result.sections.seo;
  const titleFinding = findById(section.findings, 'seo.metadata:title');
  const descFinding = findById(section.findings, 'seo.metadata:meta-description');
  const canonFinding = findById(section.findings, 'seo.metadata:canonical');
  const ogFinding = findById(section.findings, 'seo.metadata:open-graph');
  const sdFinding = findById(section.findings, 'seo.structured_data:structured-data');

  return {
    title: titleFinding?.status === 'verified' ? String(titleFinding.value ?? '') : null,
    hasDescription: descFinding?.status === 'verified',
    hasCanonical: canonFinding?.status === 'verified',
    hasOpenGraph: ogFinding?.status === 'verified',
    hasStructuredData: sdFinding?.status === 'verified',
  };
}

function extractInfraSummary(result: AnalysisResult): InfraSummary {
  const archFindings = result.sections.architecture.findings;
  const techFindings = result.sections.technology.findings;

  const platforms: string[] = [];
  const cdn: string[] = [];
  const server: string[] = [];

  // From architecture.platform findings
  for (const f of archFindings) {
    if (f.source === 'architecture.platform' && f.detected && f.value) {
      const val = String(f.value);
      if (f.details?.type === 'cdn') cdn.push(val);
      else platforms.push(val);
    }
  }

  // From technology.stack - CDN/hosting categories
  for (const f of techFindings) {
    if (f.source === 'technology.stack' && f.detected) {
      const name = f.name;
      if (['Cloudflare', 'AWS CloudFront', 'Fastly', 'Vercel', 'Netlify', 'GitHub Pages'].includes(name)) {
        if (!cdn.includes(name) && !platforms.includes(name)) {
          if (name.includes('Front') || name === 'Cloudflare' || name === 'Fastly') cdn.push(name);
          else platforms.push(name);
        }
      }
    }
  }

  // From technology.language - server software
  for (const f of techFindings) {
    if (f.source === 'technology.language' && f.detected && f.value) {
      server.push(String(f.value));
    }
  }

  return { platforms, cdn, server };
}

function findById(findings: Finding[], id: string): Finding | undefined {
  return findings.find((f) => f.id === id);
}

function findNumericValue(findings: Finding[], id: string): number | null {
  const f = findById(findings, id);
  if (!f || typeof f.value !== 'number') return null;
  return f.value;
}
