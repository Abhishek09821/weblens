import { InfoIcon } from 'lucide-react';

import { EvidencePopover } from '@/components/sections/EvidencePopover';
import { FindingStatusBadge } from '@/components/sections/StatusBadge';
import { formatFindingValue } from '@/lib/format/status';
import { humanizeLabel } from '@/lib/format/labels';
import type { Finding } from '@/types/analysis';

/**
 * Findings grouped by category.
 *
 * Negative findings are shown with their reason rather than hidden. "We looked and did not find
 * this, and here is what that does and does not mean" is the most useful thing this tool can say,
 * and it is the part most audit tools leave out.
 */
export function FindingsTable({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return <p className="text-sm text-muted-foreground">No findings were produced.</p>;
  }

  const groups = new Map<string, Finding[]>();
  for (const finding of [...findings].sort(
    (a, b) => a.category.localeCompare(b.category) || a.id.localeCompare(b.id),
  )) {
    const bucket = groups.get(finding.category) ?? [];
    bucket.push(finding);
    groups.set(finding.category, bucket);
  }

  return (
    <div className="space-y-6">
      {[...groups.entries()].map(([category, group]) => (
        <section key={category} aria-labelledby={`category-${category}`}>
          <h3
            id={`category-${category}`}
            className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {humanizeLabel(category)}
          </h3>
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">{humanizeLabel(category)} findings</caption>
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                  <th scope="col" className="px-3 py-2 font-medium">
                    Finding
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Status
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Value
                  </th>
                  <th scope="col" className="w-10 px-3 py-2 font-medium">
                    <span className="sr-only">Evidence</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {group.map((finding) => (
                  <tr key={finding.id} className="border-b border-border/60 last:border-0 align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium">{finding.name}</div>
                      {finding.reason && (
                        <p className="mt-0.5 text-xs text-muted-foreground">{finding.reason}</p>
                      )}
                      {finding.limitations.length > 0 && (
                        <p className="mt-1 flex items-start gap-1 text-xs text-muted-foreground/80">
                          <InfoIcon className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                          <span>{finding.limitations.join(' ')}</span>
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <FindingStatusBadge status={finding.status} />
                    </td>
                    <td className="max-w-[26rem] px-3 py-2">
                      <span className="block break-words font-mono text-[13px]">
                        {formatFindingValue(finding)}
                      </span>
                      {finding.values.length > 1 && finding.value !== null && (
                        <span className="mt-0.5 block break-words text-xs text-muted-foreground">
                          {finding.values.join(', ')}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <EvidencePopover evidence={finding.evidence} label={finding.name} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
