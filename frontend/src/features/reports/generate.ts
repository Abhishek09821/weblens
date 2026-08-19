/**
 * Report generation: `AnalysisResult` in, files out.
 *
 * Runs entirely in the browser from the result stored in IndexedDB, so exports keep working after a
 * restart with the backend stopped (docs/blueprint/decisions.md D2). Pure and deterministic: the
 * same result always produces byte-identical files.
 */
import { slugifyHost, timestampSlug } from '@/lib/format/values';
import type { AnalysisResult, SectionKey } from '@/types/analysis';

import { renderAnalysisJson } from './json';
import { DEFAULT_RENDER_OPTIONS, type RenderContext, type RenderOptions } from './markdown/shared';
import { REPORT_DEFINITIONS, definitionForSection } from './markdown/renderers';

export interface ReportFile {
  path: string;
  contents: string;
  bytes: number;
}

export interface ReportManifest {
  scan_id: string;
  target: string;
  generated_at: string;
  engine_version: string;
  schema_version: string;
  files: { path: string; bytes: number }[];
}

export interface ReportBundle {
  files: ReportFile[];
  manifest: ReportManifest;
  suggestedName: string;
}

function file(path: string, contents: string): ReportFile {
  return { path, contents, bytes: new TextEncoder().encode(contents).length };
}

function contextFor(
  result: AnalysisResult,
  sectionKey: SectionKey,
  options: RenderOptions,
): RenderContext {
  return { result, sectionKey, section: result.sections[sectionKey], options };
}

/** Render one section's Markdown document. */
export function renderSectionReport(
  result: AnalysisResult,
  sectionKey: SectionKey,
  options: RenderOptions = DEFAULT_RENDER_OPTIONS,
): ReportFile | null {
  const definition = definitionForSection(sectionKey);
  if (!definition) return null;
  const contents = definition.render(contextFor(result, sectionKey, options));
  return file(definition.file, contents);
}

/** Render every report file for a result. */
export function buildReportBundle(
  result: AnalysisResult,
  options: RenderOptions = DEFAULT_RENDER_OPTIONS,
): ReportBundle {
  const files: ReportFile[] = REPORT_DEFINITIONS.map((definition) =>
    file(definition.file, definition.render(contextFor(result, definition.sections[0]!, options))),
  );

  files.push(file('analysis.json', renderAnalysisJson(result)));

  const manifest: ReportManifest = {
    scan_id: result.scan.scan_id,
    target: result.target.normalized_url,
    generated_at: new Date().toISOString(),
    engine_version: result.scan.engine_version,
    schema_version: result.schema_version,
    files: files.map(({ path, bytes }) => ({ path, bytes })),
  };

  files.push(file('README.md', renderBundleReadme(result, manifest)));

  return {
    files,
    manifest,
    suggestedName: `weblens-${slugifyHost(result.target.host)}-${timestampSlug(result.scan.created_at)}`,
  };
}

function renderBundleReadme(result: AnalysisResult, manifest: ReportManifest): string {
  const lines = [
    `# WebLens report — ${result.target.host}`,
    '',
    `Generated ${manifest.generated_at} by WebLens engine ${manifest.engine_version} ` +
      `(result schema ${manifest.schema_version}).`,
    '',
    '## Contents',
    '',
    ...manifest.files.map(({ path, bytes }) => `- \`${path}\` — ${bytes} bytes`),
    '',
    '## How to read the findings',
    '',
    'Each finding carries a status:',
    '',
    '- **Verified** — directly observed in the evidence collected from the page.',
    '- **Inferred** — derived from indirect signals, which are listed alongside.',
    '- **Not detected** — evidence was collected and the signal was absent. This is not the same',
    '  as "not used": server-rendered or bundled technologies are often invisible from outside.',
    '- **Not determinable** — the property cannot be observed externally.',
    '- **Unable to verify** — the evidence needed for the check was not collected in this scan.',
    '',
    'Sections marked *not in this build* have no analyzer implemented yet. Nothing was inferred in',
    'their place.',
    '',
    'Statements under an **Interpretation** heading are readings of measured values, not',
    'observations, and each cites the findings it came from.',
    '',
    '## Scope',
    '',
    '- One URL, one run, one moment in time, from one network location.',
    '- Passive observation only: no forms submitted, no authentication attempted, no access',
    '  controls tested.',
    '- `analysis.json` is the machine-readable source of truth for everything in this bundle.',
    '',
  ];
  return lines.join('\n');
}
