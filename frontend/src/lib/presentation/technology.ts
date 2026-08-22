/** Presentation model for the consolidated V2 Tech Stack report. */
import { humanizeLabel } from '@/lib/format/labels';
import type { AnalysisResult, EvidenceRef, Finding, FindingStatus } from '@/types/analysis';

export interface TechPresentation {
  categories: TechCategory[];
  hypotheses: TechHypothesis[];
  unknowns: TechUnknown[];
}

export interface TechCategory {
  title: TechCategoryName;
  items: TechItem[];
}

export interface TechItem {
  name: string;
  status: FindingStatus;
  description: string;
  signals: string[];
  limitations: string[];
  findingId: string;
  evidence: EvidenceRef[];
  source: string;
}

export interface TechHypothesis {
  findingId: string;
  hypothesis: string;
  reasoning: string | null;
  basis: Array<{ label: string; url: string | null }>;
  limitations: string[];
  evidence: EvidenceRef[];
}

export interface TechUnknown {
  findingId: string;
  name: string;
  status: Extract<FindingStatus, 'not_detected' | 'not_determinable' | 'unable_to_verify'>;
  reason: string;
  limitations: string[];
}

type TechCategoryName =
  | 'Frontend'
  | 'Rendering'
  | 'Styling'
  | 'Libraries'
  | 'Infrastructure'
  | 'Backend signals'
  | 'Third-party services'
  | 'Analytics'
  | 'CDN / hosting'
  | 'Potential backend architecture';

const CATEGORY_ORDER: TechCategoryName[] = [
  'Frontend',
  'Rendering',
  'Styling',
  'Libraries',
  'Infrastructure',
  'Backend signals',
  'Third-party services',
  'Analytics',
  'CDN / hosting',
  'Potential backend architecture',
];

const LIBRARIES = new Set([
  'jQuery',
  'Lodash',
  'GSAP',
  'Three.js',
  'Turbo/Hotwire',
  'Stimulus',
  'Alpine.js',
  'HTMX',
]);
const ANALYTICS = new Set([
  'Google Analytics',
  'Google Tag Manager',
  'Meta Pixel',
  'Facebook Pixel',
  'Segment',
  'Mixpanel',
  'Hotjar',
  'Microsoft Clarity',
]);
const CDN_HOSTING = new Set([
  'Cloudflare',
  'Vercel',
  'Netlify',
  'AWS CloudFront',
  'Fastly',
  'GitHub Pages',
]);
const THIRD_PARTY = new Set(['Google Fonts', 'Adobe Fonts', 'Intercom', 'Stripe']);

export function buildTechPresentation(result: AnalysisResult): TechPresentation {
  const findings = result.sections.technology.findings;
  const categories = new Map<TechCategoryName, TechItem[]>();

  for (const finding of findings) {
    if (!isDeterministicClaim(finding)) continue;
    const category = categoryFor(finding);
    if (!category) continue;

    const item: TechItem = {
      name: displayName(finding),
      status: finding.status,
      description: descriptionFor(finding),
      signals: signalSummary(finding),
      limitations: finding.limitations,
      findingId: finding.id,
      evidence: finding.evidence,
      source: finding.source,
    };
    const group = categories.get(category) ?? [];
    if (!group.some((existing) => existing.name === item.name)) group.push(item);
    categories.set(category, group);
  }

  const byId = new Map(findings.map((finding) => [finding.id, finding.name]));
  const hypotheses = findings
    .filter((finding) => finding.status === 'ai_inferred')
    .map((finding) => buildHypothesis(finding, byId));
  const unknowns = findings
    .filter(isUnknown)
    .map((finding) => ({
      findingId: finding.id,
      name: finding.name,
      status: finding.status,
      reason: finding.reason ?? 'No public evidence was available for this conclusion.',
      limitations: finding.limitations,
    }));

  return {
    categories: CATEGORY_ORDER.filter((title) => categories.has(title)).map((title) => ({
      title,
      items: categories.get(title) ?? [],
    })),
    hypotheses,
    unknowns,
  };
}

function isDeterministicClaim(finding: Finding): boolean {
  if (
    finding.status !== 'verified' &&
    finding.status !== 'strongly_inferred' &&
    finding.status !== 'inferred'
  ) {
    return false;
  }
  return (
    finding.detected === true ||
    finding.source === 'architecture.rendering' ||
    finding.source === 'architecture.runtime'
  );
}

function categoryFor(finding: Finding): TechCategoryName | null {
  const name = displayName(finding);
  if (ANALYTICS.has(name)) return 'Analytics';
  if (CDN_HOSTING.has(name) || finding.details.type === 'cdn') return 'CDN / hosting';
  if (THIRD_PARTY.has(name)) return 'Third-party services';
  if (LIBRARIES.has(name)) return 'Libraries';

  switch (finding.source) {
    case 'technology.framework':
      return 'Frontend';
    case 'technology.styling':
      return 'Styling';
    case 'technology.language':
      return 'Backend signals';
    case 'architecture.rendering':
      return 'Rendering';
    case 'architecture.platform':
      return 'Infrastructure';
    case 'architecture.runtime':
      return 'Potential backend architecture';
    case 'network.third_parties':
      return 'Third-party services';
    case 'technology.stack':
      return finding.category === 'framework' ? 'Frontend' : 'Libraries';
    default:
      return null;
  }
}

function displayName(finding: Finding): string {
  if (
    typeof finding.value === 'string' &&
    ['Hosting platform', 'Server-side technology', 'Rendering strategy'].includes(finding.name)
  ) {
    return `${finding.name}: ${humanizeLabel(finding.value)}`;
  }
  return finding.name.replace('Platform: ', '');
}

function descriptionFor(finding: Finding): string {
  if (finding.reason) return finding.reason;
  if (finding.values.length > 0) return finding.values.slice(0, 5).join(', ');
  if (finding.value !== null && finding.value !== undefined && typeof finding.value !== 'boolean') {
    return String(finding.value);
  }
  return `Observable signals associated with ${displayName(finding)}.`;
}

function signalSummary(finding: Finding): string[] {
  return finding.evidence.slice(0, 4).map((evidence) => humanizeEvidence(evidence));
}

function humanizeEvidence(evidence: EvidenceRef): string {
  const excerpt = evidence.excerpt?.slice(0, 120);
  switch (evidence.kind) {
    case 'http_header':
      return excerpt ? `Response header: ${excerpt}` : `Response header at ${evidence.source}`;
    case 'script_url':
      return excerpt ? `Script: ${excerpt}` : `Script observed at ${evidence.source}`;
    case 'runtime_global':
      return excerpt ? `Runtime global: ${excerpt}` : `Runtime signal at ${evidence.source}`;
    case 'network_request':
      return excerpt ? `Network request: ${excerpt}` : `Network request at ${evidence.source}`;
    case 'meta_tag':
      return excerpt ? `Meta tag: ${excerpt}` : `Meta tag at ${evidence.source}`;
    default:
      return excerpt ?? `${humanizeLabel(evidence.kind)} from ${evidence.source}`;
  }
}

function buildHypothesis(finding: Finding, byId: Map<string, string>): TechHypothesis {
  const reasoningEvidence = finding.evidence.find((evidence) => evidence.kind === 'ai_reasoning');
  const rawBasis = reasoningEvidence?.detail.basis;
  const entries = Array.isArray(rawBasis)
    ? rawBasis.filter((entry): entry is string => typeof entry === 'string')
    : typeof rawBasis === 'string'
      ? rawBasis.split(',').map((entry) => entry.trim()).filter(Boolean)
      : [];

  return {
    findingId: finding.id,
    hypothesis: finding.name,
    reasoning: reasoningEvidence?.excerpt ?? finding.reason ?? null,
    basis: entries.map((entry) => ({
      label: byId.get(entry) ?? entry,
      url: /^https:\/\//i.test(entry) ? entry : null,
    })),
    limitations: finding.limitations,
    evidence: finding.evidence,
  };
}

function isUnknown(
  finding: Finding,
): finding is Finding & {
  status: Extract<FindingStatus, 'not_detected' | 'not_determinable' | 'unable_to_verify'>;
} {
  return (
    finding.status === 'not_detected' ||
    finding.status === 'not_determinable' ||
    finding.status === 'unable_to_verify'
  );
}
