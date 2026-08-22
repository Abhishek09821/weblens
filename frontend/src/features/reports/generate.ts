/** Browser-only deterministic report generation from the stored V2 result. */
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

/** Render one of the four V2 Markdown documents. */
export function renderSectionReport(
  result: AnalysisResult,
  sectionKey: SectionKey,
  options: RenderOptions = DEFAULT_RENDER_OPTIONS,
): ReportFile {
  const definition = definitionForSection(sectionKey);
  return file(
    definition.file,
    definition.render(contextFor(result, definition.section, options)),
  );
}

/** Render exactly four Markdown reports plus the machine-readable source of truth. */
export function buildReportBundle(
  result: AnalysisResult,
  options: RenderOptions = DEFAULT_RENDER_OPTIONS,
): ReportBundle {
  const files = REPORT_DEFINITIONS.map((definition) =>
    file(
      definition.file,
      definition.render(contextFor(result, definition.section, options)),
    ),
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

  return {
    files,
    manifest,
    suggestedName: `weblens-${slugifyHost(result.target.host)}-${timestampSlug(result.scan.created_at)}`,
  };
}
