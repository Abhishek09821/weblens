/**
 * Renderer registry.
 *
 * Adding a section report means one entry here and one renderer function. Sections without a
 * specialised renderer use the standard document, which already handles findings, interpretations,
 * evidence, errors, limitations, and the unavailable case - so a section is never missing a file.
 */
import type { SectionKey } from '@/types/analysis';

import { runContextBlock, standardDocument, type RenderContext } from '../shared';

import { renderArchitecture } from './architecture';
import { renderSecurity } from './security';
import { renderSeo } from './seo';

export type SectionRenderer = (ctx: RenderContext) => string;

export interface ReportDefinition {
  /** File name inside the bundle. */
  file: string;
  title: string;
  /** Sections this document covers; the first is the primary one. */
  sections: SectionKey[];
  render: SectionRenderer;
}

/** Performance and design reports must always state the conditions of measurement. */
const withRunContext =
  (title: string): SectionRenderer =>
  (ctx) =>
    standardDocument(ctx, title, runContextBlock(ctx.result));

export const REPORT_DEFINITIONS: readonly ReportDefinition[] = [
  {
    file: 'design.md',
    title: 'Design',
    sections: ['design'],
    render: withRunContext('Design'),
  },
  {
    file: 'techstack.md',
    title: 'Technology stack',
    sections: ['technology'],
    render: (ctx) => standardDocument(ctx, 'Technology stack'),
  },
  {
    file: 'security.md',
    title: 'Security',
    sections: ['security'],
    render: renderSecurity,
  },
  {
    file: 'performance.md',
    title: 'Performance',
    sections: ['performance'],
    render: withRunContext('Performance'),
  },
  {
    file: 'accessibility.md',
    title: 'Accessibility',
    sections: ['accessibility'],
    render: (ctx) => standardDocument(ctx, 'Accessibility'),
  },
  {
    file: 'seo.md',
    title: 'SEO',
    sections: ['seo'],
    render: renderSeo,
  },
  {
    file: 'architecture.md',
    title: 'Architecture and runtime',
    sections: ['architecture', 'network'],
    render: renderArchitecture,
  },
] as const;

export function definitionForSection(sectionKey: SectionKey): ReportDefinition | undefined {
  return REPORT_DEFINITIONS.find((definition) => definition.sections[0] === sectionKey);
}
