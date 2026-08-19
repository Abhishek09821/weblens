import { securityScoreSchema } from '@/types/analysis';

import { blockquote, bullets, heading, keyValueTable, section as join, table } from '../kit';
import { standardDocument, type RenderContext } from '../shared';

/**
 * Security report.
 *
 * The score is the only score WebLens produces, and it only earns that place by being auditable:
 * the rule table, the excluded rules, and the band caps are all printed, so a reader can
 * reconstruct the number and see exactly what was and was not evaluated.
 *
 * The disclaimer comes from the payload rather than being written here, so the API, the UI, and
 * this report cannot drift into saying different things.
 */
export function renderSecurity(ctx: RenderContext): string {
  const data = ctx.section.data;
  const scoreValue =
    data && typeof data === 'object' ? (data as { score?: unknown }).score : undefined;
  const parsed = securityScoreSchema.safeParse(scoreValue);

  if (!parsed.success) {
    return standardDocument(
      ctx,
      'Security',
      join(
        heading(2, 'Observable Security Posture'),
        'No posture score was produced for this scan.',
        bullets([
          'A score is only emitted when enough rules could be evaluated to make the ratio meaningful.',
          'The findings below still describe what was observed.',
        ]),
      ),
    );
  }

  const score = parsed.data;
  const rows = [...score.rules]
    .sort((a, b) => b.weight - a.weight || a.id.localeCompare(b.id))
    .map((rule) => [
      rule.id,
      rule.title,
      rule.category,
      rule.outcome,
      `${rule.awarded} / ${rule.weight}`,
      rule.rationale,
      rule.recommendation ?? '',
    ]);

  const scoreBlock = join(
    heading(2, score.label),
    blockquote(score.disclaimer),
    keyValueTable([
      ['Score', `${score.percentage}%`],
      ['Points awarded', score.points_awarded],
      ['Points applicable', score.points_applicable],
      ['Band', score.band_phrase],
      ['Methodology version', score.methodology_version],
    ]),
  );

  const capsBlock =
    score.applied_caps.length > 0
      ? join(
          heading(3, 'Band caps applied'),
          'A dominant observation limited the band regardless of the percentage.',
          table(
            ['Rule', 'Band ceiling', 'Reason'],
            score.applied_caps.map((cap) => [cap.rule_id, cap.cap, cap.reason]),
          ),
        )
      : '';

  const excludedBlock =
    score.excluded_rules.length > 0
      ? join(
          heading(3, 'Rules excluded from the score'),
          'These rules were left out of both the numerator and the denominator, so the ratio is auditable.',
          table(
            ['Rule', 'Outcome', 'Reason'],
            score.excluded_rules.map((rule) => [rule.id, rule.outcome, rule.reason]),
          ),
        )
      : '';

  const rulesBlock = join(
    heading(3, 'Rule results'),
    table(
      ['Rule', 'Title', 'Category', 'Outcome', 'Points', 'Rationale', 'Recommendation'],
      rows,
    ),
  );

  return standardDocument(ctx, 'Security', scoreBlock, capsBlock, excludedBlock, rulesBlock);
}
