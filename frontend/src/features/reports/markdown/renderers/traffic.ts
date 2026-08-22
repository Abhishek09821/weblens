import { findingStatusLabel } from '@/lib/format/status';
import { trafficPayloadSchema, type Finding } from '@/types/analysis';
import { findingStatusToVerdict, verdictLabel } from '@/types/analysis';

import { blockquote, heading, keyValueTable, section as join, table } from '../kit';
import { aiVerdictBlock, evidenceQualityBlock, standardDocument, type RenderContext } from '../shared';

/** Traffic and Popularity report matching the spec template. */
export function renderTraffic(ctx: RenderContext): string {
  const parsed = trafficPayloadSchema.safeParse(ctx.section.data);
  const payload = parsed.success ? parsed.data : null;
  const findings = ctx.section.findings;
  const deterministic = findings.filter((f) => f.status !== 'ai_inferred');
  const aiFindings = findings.filter((f) => f.status === 'ai_inferred');

  const popularity = deterministic.filter((f) => f.category === 'popularity');
  const signals = deterministic.filter((f) => f.category === 'analytics');
  const hasEstimate = popularity.some(
    (f) =>
      ['verified', 'strongly_inferred', 'inferred'].includes(f.status) &&
      (f.value !== null || f.values.length > 0),
  );

  const popularityVerdict = join(
    heading(2, 'Popularity Verdict'),
    keyValueTable([
      ['Data provider', payload?.provider_name ?? 'none configured'],
      ['Provider available', payload?.provider_available ?? false],
    ]),
    hasEstimate
      ? findingsTable(popularity)
      : blockquote(
          'Traffic estimates are unavailable. WebLens does not fabricate visit counts, rank, or a popularity band from passive page observations.',
        ),
    !hasEstimate && popularity.length > 0 ? findingsTable(popularity) : '',
  );

  const trafficEstimate = join(
    heading(2, 'Traffic Estimate'),
    hasEstimate
      ? '_See popularity verdict above._'
      : '_No traffic estimate could be produced from available evidence._',
  );

  const publicSignals = join(
    heading(2, 'Analytics Observations'),
    'Client-side analytics observed during this visit. They indicate measurement tooling, not traffic volume.',
    signals.length > 0 ? findingsTable(signals) : '_No analytics signals were detected._',
  );

  const confidenceBlock = join(
    heading(2, 'Confidence'),
    hasEstimate
      ? 'Traffic estimates are backed by a configured data provider. See individual finding verdicts for confidence levels.'
      : 'No traffic data provider is configured. Estimates cannot be produced without a credible external source.',
  );

  return standardDocument(
    ctx,
    'Traffic and Popularity',
    evidenceQualityBlock(ctx.result, 'traffic'),
    popularityVerdict,
    trafficEstimate,
    publicSignals,
    aiVerdictBlock(aiFindings, 'AI / Research Verdicts'),
    confidenceBlock,
  );
}

function findingsTable(findings: Finding[]): string {
  return table(
    ['Signal', 'Verdict', 'Value', 'Source', 'Limitations'],
    findings.map((f) => [
      f.name,
      verdictLabel(findingStatusToVerdict(f.status)),
      value(f),
      f.evidence.map((e) => e.source).join(', ') || f.source,
      [f.reason, ...f.limitations].filter(Boolean).join(' '),
    ]),
  );
}

function value(finding: Finding): string {
  if (finding.value !== null && finding.value !== undefined) return String(finding.value);
  return finding.values.length > 0 ? finding.values.join(', ') : '—';
}
