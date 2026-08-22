import { ExternalLinkIcon } from 'lucide-react';

import { EvidencePopover } from '@/components/sections/EvidencePopover';
import { FindingsTable } from '@/components/sections/FindingsTable';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { securityPayloadSchema, type RuleOutcome, type Section } from '@/types/analysis';

const OUTCOME_VARIANT: Record<RuleOutcome, 'verified' | 'inferred' | 'attention' | 'muted'> = {
  pass: 'verified',
  partial: 'inferred',
  fail: 'attention',
  not_applicable: 'muted',
  unknown: 'muted',
};

/** Passive externally observable security report. It never claims to prove a site is secure. */
export function SecurityDetails({ section }: { section: Section }) {
  const parsed = securityPayloadSchema.safeParse(section.data);
  const score = parsed.success ? parsed.data.score : null;

  return (
    <div className="space-y-4">
      {score ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{score.label}</CardTitle>
              <CardDescription>{score.disclaimer}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="font-mono text-3xl font-semibold tabular-nums">
                  {score.percentage}%
                </span>
                <Badge variant="outline">{score.band_phrase}</Badge>
                <span className="text-xs text-muted-foreground">
                  {score.points_awarded} of {score.points_applicable} applicable points · methodology{' '}
                  {score.methodology_version}
                </span>
              </div>

              <div
                className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
                role="img"
                aria-label={`${score.percentage}% of applicable passive-observation points`}
              >
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.min(Math.max(score.percentage, 0), 100)}%` }}
                />
              </div>

              <p className="text-xs font-medium text-muted-foreground">
                This score summarizes a single passive scan. It is not proof that the website is secure.
              </p>

              {score.applied_caps.length > 0 && (
                <div className="rounded-md border border-status-attention/40 bg-status-attention/5 p-3">
                  <p className="text-xs font-medium">Band limited by a dominant observation</p>
                  <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                    {score.applied_caps.map((cap) => (
                      <li key={cap.rule_id}>
                        <code className="font-mono">{cap.rule_id}</code> — {cap.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Security rule results</caption>
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                  <th scope="col" className="px-3 py-2 font-medium">Rule</th>
                  <th scope="col" className="px-3 py-2 font-medium">Outcome</th>
                  <th scope="col" className="px-3 py-2 font-medium">Points</th>
                  <th scope="col" className="px-3 py-2 font-medium">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {score.rules.map((rule) => (
                  <tr key={rule.id} className="border-b border-border/60 align-top last:border-0">
                    <td className="px-3 py-2">
                      <div className="flex items-start gap-1">
                        <div>
                          <div className="font-medium">{rule.title}</div>
                          <code className="font-mono text-[11px] text-muted-foreground">{rule.id}</code>
                        </div>
                        <EvidencePopover evidence={rule.evidence} label={rule.title} />
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant={OUTCOME_VARIANT[rule.outcome]}>
                        {rule.outcome.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs tabular-nums">
                      {rule.awarded}/{rule.weight}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {rule.rationale}
                      {rule.recommendation && (
                        <span className="mt-1 block text-foreground/80">{rule.recommendation}</span>
                      )}
                      {rule.reference && (
                        <a
                          href={rule.reference}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="mt-1 inline-flex items-center gap-1 underline-offset-2 hover:underline"
                        >
                          Reference
                          <ExternalLinkIcon className="size-3" aria-hidden="true" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {score.excluded_rules.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Rules excluded from the score</CardTitle>
                <CardDescription>
                  Excluded from both numerator and denominator so the ratio stays auditable.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {score.excluded_rules.map((rule) => (
                    <li key={rule.id}>
                      <code className="font-mono">{rule.id}</code> — {rule.outcome.replace(/_/g, ' ')}:{' '}
                      {rule.reason}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Observable Security Posture</CardTitle>
            <CardDescription>
              No posture score was produced. A score is emitted only when enough passive checks
              were evaluable for the ratio to be meaningful.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {section.findings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Passive security observations</CardTitle>
            <CardDescription>
              Headers, cookies, TLS, exposed information, mixed content, and third-party observations
              are shown only when the corresponding evidence was collected.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FindingsTable findings={section.findings} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
