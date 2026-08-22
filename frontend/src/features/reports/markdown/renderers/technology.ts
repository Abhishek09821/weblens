import { findingStatusLabel } from '@/lib/format/status';
import { buildTechPresentation } from '@/lib/presentation/technology';
import type { Finding } from '@/types/analysis';
import { findingStatusToVerdict, verdictLabel } from '@/types/analysis';

import { bullets, heading, section as join, table } from '../kit';
import { aiVerdictBlock, evidenceQualityBlock, standardDocument, type RenderContext } from '../shared';

/** Website Technical Stack report matching the spec template. */
export function renderTechnology(ctx: RenderContext): string {
  const presentation = buildTechPresentation(ctx.result);
  const findings = ctx.section.findings;

  const categoryBlocks = presentation.categories.map((category) =>
    join(
      heading(2, category.title),
      table(
        ['Technology / signal', 'Verdict', 'Evidence', 'Limitations'],
        category.items.map((item) => [
          item.name,
          verdictLabel(findingStatusToVerdict(item.status)),
          item.signals.join(' ') || item.source,
          item.limitations.join(' '),
        ]),
      ),
    ),
  );

  const hypotheses = join(
    heading(2, 'Architecture Hypothesis'),
    presentation.hypotheses.length === 0
      ? '_No AI architecture hypothesis was produced._'
      : presentation.hypotheses
          .map((hypothesis) =>
            join(
              heading(3, hypothesis.hypothesis),
              `**Verdict:** AI Inferred — this is a hypothesis, not a verified detection.`,
              hypothesis.reasoning ? `**Reasoning:** ${hypothesis.reasoning}` : null,
              hypothesis.basis.length > 0
                ? join(
                    '**Evidence basis:**',
                    bullets(
                      hypothesis.basis.map((b) =>
                        b.url ? `[${b.label}](${b.url})` : `\`${b.label}\``,
                      ),
                    ),
                  )
                : null,
              hypothesis.limitations.length > 0
                ? join('**Limitations:**', bullets(hypothesis.limitations))
                : null,
            ),
          )
          .join('\n\n'),
  );

  const unknowns = join(
    heading(2, 'Unknown / Not Publicly Determinable'),
    presentation.unknowns.length === 0
      ? '_No explicit unknowns were reported._'
      : table(
          ['Property', 'Verdict', 'Reason', 'Limitations'],
          presentation.unknowns.map((unknown) => [
            unknown.name,
            verdictLabel(findingStatusToVerdict(unknown.status)),
            unknown.reason,
            unknown.limitations.join(' '),
          ]),
        ),
  );

  const evidenceQuality = join(
    heading(2, 'Verdicts'),
    table(
      ['Evidence state', 'Count'],
      [
        ['Verified', count('verified')],
        ['Strongly Supported (inferred)', count('strongly_inferred')],
        ['Likely (inferred)', count('inferred')],
        ['AI Inferred', count('ai_inferred')],
        ['Not Detected', count('not_detected')],
        ['Not Publicly Determinable', count('not_determinable')],
        ['Unable to Verify', count('unable_to_verify')],
      ],
    ),
  );

  // Research sources from AI findings
  const aiFindings = findings.filter((f) => f.status === 'ai_inferred');
  const researchSources = aiFindings
    .flatMap((f) => f.evidence)
    .filter((e) => e.kind === 'research_source' || e.kind === 'ai_reasoning')
    .map((e) => e.excerpt ?? e.source)
    .filter(Boolean);

  const researchBlock = join(
    heading(2, 'Research Sources'),
    researchSources.length === 0
      ? '_No external research sources were consulted._'
      : bullets([...new Set(researchSources)].slice(0, 15)),
  );

  return standardDocument(
    ctx,
    'Website Technical Stack',
    evidenceQualityBlock(ctx.result, 'technology'),
    ...categoryBlocks,
    hypotheses,
    evidenceQuality,
    unknowns,
    researchBlock,
  );

  function count(status: (typeof findings)[number]['status']): number {
    return findings.filter((f) => f.status === status).length;
  }
}
