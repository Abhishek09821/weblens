import type { SectionKey } from '@/types/analysis';

const SECTION_LABELS: Record<SectionKey, string> = {
  design: 'Design',
  technology: 'Tech Stack',
  security: 'Security',
  traffic: 'Traffic',
};

const SECTION_SUMMARIES: Record<SectionKey, string> = {
  design: 'Observed structure, visual system, responsive behavior and implementation clues.',
  technology: 'Verified and inferred technologies, infrastructure and public backend signals.',
  security: 'Passive security observations and posture, with scope and limitations.',
  traffic: 'Provider-sourced popularity and traffic signals without fabricated estimates.',
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
