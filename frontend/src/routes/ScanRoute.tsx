import { CircleAlertIcon, ExternalLinkIcon, TriangleAlertIcon } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';

import { ExportMenu } from '@/components/reports/ExportMenu';
import { SectionNav } from '@/components/sections/SectionNav';
import { SectionPanel } from '@/components/sections/SectionPanel';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useStoredResult } from '@/features/history/useScanLibrary';
import { formatDuration, formatTimestamp, truncateMiddle } from '@/lib/format/values';
import { loadPrefs } from '@/lib/prefs/prefs';
import { SECTION_KEYS, type SectionKey } from '@/types/analysis';

export function ScanRoute() {
  const { scanId, sectionKey } = useParams<{ scanId: string; sectionKey?: string }>();
  const navigate = useNavigate();
  const stored = useStoredResult(scanId);

  const active: SectionKey =
    sectionKey && (SECTION_KEYS as readonly string[]).includes(sectionKey)
      ? (sectionKey as SectionKey)
      : loadPrefs().default_section;

  if (stored.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!stored.data) {
    return (
      <Alert variant="warning">
        <TriangleAlertIcon className="size-4" />
        <AlertTitle>This scan is not stored in this browser</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            Scans live only in the browser profile that ran them. If this link came from elsewhere,
            or the scan was deleted, run a new analysis.
          </p>
          <Button variant="outline" size="sm" onClick={() => navigate('/')}>
            Back to analyze
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const result = stored.data;
  const scan = result.scan;
  const target = result.target;
  const degraded = result.errors.length > 0 || scan.status === 'completed_with_errors';

  return (
    <div className="space-y-5">
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight">{target.host}</h1>
              <Badge variant="outline" className="font-mono">
                {scan.status.replace(/_/g, ' ')}
              </Badge>
              {target.http_status !== null && target.http_status !== undefined && (
                <Badge variant="muted" className="font-mono">
                  HTTP {target.http_status}
                </Badge>
              )}
            </div>
            <a
              href={target.final_url ?? target.normalized_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-1 inline-flex items-center gap-1 font-mono text-xs text-muted-foreground hover:text-foreground"
            >
              {truncateMiddle(target.final_url ?? target.normalized_url, 96)}
              <ExternalLinkIcon className="size-3" aria-hidden="true" />
            </a>
          </div>
          <ExportMenu result={result} />
        </div>

        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
          <MetaItem label="Scanned" value={formatTimestamp(scan.finished_at ?? scan.created_at)} />
          <MetaItem label="Duration" value={formatDuration(scan.duration_ms)} />
          <MetaItem label="Engine" value={scan.engine_version} />
          <MetaItem label="Schema" value={result.schema_version} />
          <MetaItem label="Collection" value={scan.run_context?.collection_mode ?? 'unknown'} />
          <MetaItem label="Scan id" value={scan.scan_id} mono />
        </dl>
      </header>

      {degraded && (
        <Alert variant="warning">
          <CircleAlertIcon className="size-4" />
          <AlertTitle>
            Completed with {result.errors.length} issue{result.errors.length === 1 ? '' : 's'}
          </AlertTitle>
          <AlertDescription>
            Affected sections state what could not be produced and why. Everything else is unaffected.
          </AlertDescription>
        </Alert>
      )}

      {result.limitations.length > 0 && (
        <Card>
          <CardContent className="pt-4">
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Scope of this scan
            </p>
            <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {result.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Separator />

      <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <SectionNav
          sections={result.sections}
          active={active}
          onSelect={(key) => navigate(`/scan/${scan.scan_id}/${key}`)}
        />
        <SectionPanel result={result} sectionKey={active} />
      </div>
    </div>
  );
}

function MetaItem({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt>{label}</dt>
      <dd className={mono ? 'font-mono text-foreground/80' : 'text-foreground/80'}>{value}</dd>
    </div>
  );
}
