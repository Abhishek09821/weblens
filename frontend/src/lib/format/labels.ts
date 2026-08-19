import type { SectionKey } from '@/types/analysis';

const SECTION_LABELS: Record<SectionKey, string> = {
  design: 'Design',
  technology: 'Technology',
  security: 'Security',
  performance: 'Performance',
  accessibility: 'Accessibility',
  seo: 'SEO',
  architecture: 'Architecture',
  network: 'Network',
};

const SECTION_SUMMARIES: Record<SectionKey, string> = {
  design: 'Colours, typography, spacing and layout as actually rendered.',
  technology: 'Products and frameworks detected from observable signals.',
  security: 'Observable security configuration and posture score.',
  performance: 'Timing and resource measurements from one lab run.',
  accessibility: 'Automated rule results and structural observations.',
  seo: 'Metadata, indexability and structured data as served.',
  architecture: 'Rendering strategy, platform indicators and runtime signals.',
  network: 'Requests, domains and transfer characteristics.',
};

export function sectionLabel(key: SectionKey): string {
  return SECTION_LABELS[key];
}

export function sectionSummary(key: SectionKey): string {
  return SECTION_SUMMARIES[key];
}

/** `response_headers` → `Response Headers` */
export function humanizeLabel(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}
