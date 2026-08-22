import { findingStatusLabel } from '@/lib/format/status';
import type { AnalysisResult, Finding } from '@/types/analysis';
import { findingStatusToVerdict, verdictLabel } from '@/types/analysis';

import { heading, section as join, table } from '../kit';
import { aiVerdictBlock, evidenceQualityBlock, runContextBlock, standardDocument, type RenderContext } from '../shared';

/** Design Reconstruction report matching the spec template. */
export function renderDesign(ctx: RenderContext): string {
  const findings = ctx.section.findings;
  const deterministic = findings.filter((f) => f.status !== 'ai_inferred');
  const aiFindings = findings.filter((f) => f.status === 'ai_inferred');

  const structure = deterministic.filter((f) => ['document', 'structure'].includes(f.category));
  const navigation = structure.filter((f) =>
    `${f.name} ${f.values.join(' ')}`.match(/header|navigation|nav|banner/i),
  );
  const layout = deterministic.filter((f) => f.category === 'layout');
  const responsive = deterministic.filter((f) => f.category === 'responsive');
  const typography = deterministic.filter((f) => f.category === 'typography');
  const colors = deterministic.filter((f) => f.category === 'color');
  const spacing = deterministic.filter((f) => f.id === 'design.layout:gap-values');
  const components = deterministic.filter(
    (f) =>
      f.category === 'forms' ||
      f.id === 'design.layout:border-radius' ||
      f.id === 'design.layout:box-shadows',
  );
  const media = deterministic.filter((f) => ['media', 'images'].includes(f.category));
  const motion = deterministic.filter((f) => f.category === 'motion');

  return standardDocument(
    ctx,
    'Design Reconstruction',
    evidenceQualityBlock(ctx.result, 'design'),
    runContextBlock(ctx.result),
    group('Page Structure', structure),
    group('Navigation', navigation),
    group('Layout System', layout),
    group('Responsive Behavior', responsive),
    group('Typography', typography),
    group('Colors', colors),
    group('Spacing', spacing),
    group('Components and Patterns', components),
    group('Media', media),
    group('Motion', motion),
    aiVerdictBlock(aiFindings, 'AI / Research Verdicts'),
  );
}

function group(title: string, findings: Finding[]): string {
  return join(
    heading(2, title),
    findings.length === 0
      ? '_No observation was available for this category._'
      : table(
          ['Observation', 'Verdict', 'Value', 'Evidence / notes'],
          findings.map((f) => [
            f.name,
            verdictLabel(findingStatusToVerdict(f.status)),
            value(f),
            f.reason ?? f.limitations.join(' '),
          ]),
        ),
  );
}

function value(finding: Finding): string {
  if (finding.value !== null && finding.value !== undefined) {
    const rendered = typeof finding.value === 'boolean' ? (finding.value ? 'yes' : 'no') : String(finding.value);
    return finding.unit && finding.unit !== 'count' ? `${rendered} ${finding.unit}` : rendered;
  }
  return finding.values.length > 0 ? finding.values.join(', ') : '—';
}
