import { findingStatusLabel } from '@/lib/format/status';
import { securityPayloadSchema, type Finding } from '@/types/analysis';
import { findingStatusToVerdict, verdictLabel } from '@/types/analysis';

import { blockquote, bullets, heading, keyValueTable, section as join, table } from '../kit';
import { aiVerdictBlock, evidenceQualityBlock, standardDocument, type RenderContext } from '../shared';

/**
 * Security Analysis report matching the spec template.
 *
 * The score is the only score WebLens produces. The disclaimer clearly states that passive
 * observations cannot establish complete security.
 */
export function renderSecurity(ctx: RenderContext): string {
  const parsed = securityPayloadSchema.safeParse(ctx.section.data);
  const score = parsed.success ? parsed.data.score : null;
  const findings = ctx.section.findings;
  const deterministic = findings.filter((f) => f.status !== 'ai_inferred');
  const aiFindings = findings.filter((f) => f.status === 'ai_inferred');

  // Group deterministic findings by category
  const tlsFindings = deterministic.filter((f) => f.source === 'security.tls');
  const headerFindings = deterministic.filter((f) => f.source === 'security.headers');
  const cookieFindings = deterministic.filter((f) => f.source === 'security.cookies');
  const mixedContent = deterministic.filter((f) => f.source === 'security.mixed_content');
  const exposure = deterministic.filter((f) => f.source === 'security.exposure');
  const thirdParty = deterministic.filter((f) => f.source === 'security.third_party');

  const disclaimerBlock = blockquote(
    'This is an externally observable assessment and is not proof of complete application security. ' +
    'No forms were submitted, no authentication was attempted, and no access controls were tested.',
  );

  const postureBlock = score
    ? join(
        heading(2, 'Observable Security Posture'),
        disclaimerBlock,
        keyValueTable([
          ['Score', `${score.percentage}%`],
          ['Band', score.band_phrase],
          ['Points', `${score.points_awarded} / ${score.points_applicable}`],
          ['Methodology', score.methodology_version],
        ]),
      )
    : join(
        heading(2, 'Observable Security Posture'),
        disclaimerBlock,
        'No posture score was produced. Individual observations are listed below.',
      );

  const rulesBlock = score && score.rules.length > 0
    ? join(
        heading(3, 'Rule Results'),
        table(
          ['Rule', 'Title', 'Category', 'Outcome', 'Points', 'Recommendation'],
          [...score.rules]
            .sort((a, b) => b.weight - a.weight)
            .map((rule) => [
              rule.id,
              rule.title,
              rule.category,
              rule.outcome,
              `${rule.awarded} / ${rule.weight}`,
              rule.recommendation ?? '',
            ]),
        ),
      )
    : '';

  return standardDocument(
    ctx,
    'Security Analysis',
    evidenceQualityBlock(ctx.result, 'security'),
    postureBlock,
    rulesBlock,
    findingsGroup('TLS', tlsFindings),
    findingsGroup('Security Headers', headerFindings),
    findingsGroup('Cookies', cookieFindings),
    findingsGroup('Mixed Content', mixedContent),
    findingsGroup('Technology Disclosure', exposure),
    findingsGroup('Third-Party Scripts', thirdParty),
    aiVerdictBlock(aiFindings, 'AI / Research Verdicts'),
  );
}

function findingsGroup(title: string, findings: Finding[]): string {
  if (findings.length === 0) return '';
  return join(
    heading(2, title),
    table(
      ['Observation', 'Verdict', 'Value', 'Notes'],
      findings.map((f) => [
        f.name,
        verdictLabel(findingStatusToVerdict(f.status)),
        renderValue(f),
        f.reason ?? '',
      ]),
    ),
  );
}

function renderValue(finding: Finding): string {
  if (finding.value !== null && finding.value !== undefined) {
    return typeof finding.value === 'boolean' ? (finding.value ? 'yes' : 'no') : String(finding.value);
  }
  return finding.values.length > 0 ? finding.values.join(', ') : '—';
}
