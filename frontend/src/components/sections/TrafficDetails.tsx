import { ActivityIcon, RadioTowerIcon } from 'lucide-react';

import { EvidencePopover } from '@/components/sections/EvidencePopover';
import { FindingStatusBadge } from '@/components/sections/StatusBadge';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { formatFindingValue } from '@/lib/format/status';
import { trafficPayloadSchema, type Section } from '@/types/analysis';

/** Traffic intelligence without substituting passive observations for audience estimates. */
export function TrafficDetails({ section }: { section: Section }) {
  const parsed = trafficPayloadSchema.safeParse(section.data);
  const provider = parsed.success ? parsed.data : null;
  const popularity = section.findings.filter((finding) => finding.category === 'popularity');
  const analytics = section.findings.filter((finding) => finding.category === 'analytics');
  const hasEstimate = popularity.some(
    (finding) =>
      (finding.status === 'verified' ||
        finding.status === 'strongly_inferred' ||
        finding.status === 'inferred') &&
      (finding.value !== null || finding.values.length > 0),
  );

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ActivityIcon className="size-4 text-primary" aria-hidden="true" />
            Popularity and traffic estimates
          </CardTitle>
          <CardDescription>
            Source provider: {provider?.provider_name ?? 'none configured'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!hasEstimate && (
            <div className="rounded-md border border-border bg-muted/30 p-3">
              <p className="text-sm font-medium">Traffic estimates unavailable</p>
              <p className="mt-1 text-xs text-muted-foreground">
                WebLens will not infer visit counts, rank, or a popularity band from page requests.
                A credible external traffic provider is required.
              </p>
            </div>
          )}

          {popularity.length > 0 ? (
            <ul className="divide-y divide-border">
              {popularity.map((finding) => (
                <li key={finding.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">{finding.name}</span>
                      <FindingStatusBadge status={finding.status} />
                    </div>
                    <div className="flex items-center gap-2">
                      {finding.value !== null && finding.value !== undefined && (
                        <span className="font-mono text-sm">{formatFindingValue(finding)}</span>
                      )}
                      <EvidencePopover evidence={finding.evidence} label={finding.name} />
                    </div>
                  </div>
                  {finding.reason && (
                    <p className="mt-1 text-xs text-muted-foreground">{finding.reason}</p>
                  )}
                  {finding.limitations.length > 0 && (
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                      {finding.limitations.map((limitation) => (
                        <li key={limitation}>{limitation}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              No traffic provider findings were produced for this scan.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <RadioTowerIcon className="size-4 text-primary" aria-hidden="true" />
            Public page signals
          </CardTitle>
          <CardDescription>
            Client-side analytics observed during this visit. These signals do not measure traffic.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {analytics.length === 0 ? (
            <p className="text-sm text-muted-foreground">No analytics signal result was produced.</p>
          ) : (
            <ul className="space-y-3">
              {analytics.map((finding) => (
                <li key={finding.id} className="rounded-md border border-border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">{finding.name}</span>
                      <FindingStatusBadge status={finding.status} />
                    </div>
                    <EvidencePopover evidence={finding.evidence} label={finding.name} />
                  </div>
                  {finding.values.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {finding.values.map((value) => (
                        <Badge key={value} variant="outline">{value}</Badge>
                      ))}
                    </div>
                  )}
                  {finding.reason && (
                    <p className="mt-1 text-xs text-muted-foreground">{finding.reason}</p>
                  )}
                  {finding.limitations.length > 0 && (
                    <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                      {finding.limitations.map((limitation) => (
                        <li key={limitation}>{limitation}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
