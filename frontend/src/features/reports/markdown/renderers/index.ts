/** Canonical V2 report registry shared by Markdown, ZIP, and export menus. */
import type { SectionKey } from '@/types/analysis';

import type { RenderContext } from '../shared';

import { renderDesign } from './design';
import { renderSecurity } from './security';
import { renderTechnology } from './technology';
import { renderTraffic } from './traffic';

export type SectionRenderer = (ctx: RenderContext) => string;

export interface ReportDefinition {
  /** File name inside the bundle. */
  file: 'design.md' | 'techstack.md' | 'security.md' | 'traffic.md';
  title: string;
  section: SectionKey;
  render: SectionRenderer;
}

export const REPORT_DEFINITIONS: readonly ReportDefinition[] = [
  { file: 'design.md', title: 'Design', section: 'design', render: renderDesign },
  {
    file: 'techstack.md',
    title: 'Tech Stack',
    section: 'technology',
    render: renderTechnology,
  },
  { file: 'security.md', title: 'Security', section: 'security', render: renderSecurity },
  { file: 'traffic.md', title: 'Traffic', section: 'traffic', render: renderTraffic },
] as const;

export function definitionForSection(sectionKey: SectionKey): ReportDefinition {
  return REPORT_DEFINITIONS.find((definition) => definition.section === sectionKey) ?? REPORT_DEFINITIONS[0];
}
