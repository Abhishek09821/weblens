import { ArrowRightIcon, DatabaseIcon, Trash2Icon } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { StatusDot } from '@/components/sections/StatusBadge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useDeleteScan,
  useQuarantinedScans,
  useScanLibrary,
} from '@/features/history/useScanLibrary';
import { formatBytes, formatRelativeTime, truncateMiddle } from '@/lib/format/values';
import type { ScanRecord } from '@/lib/db/types';
import { SECTION_KEYS } from '@/types/analysis';

/**
 * Locally stored scans.
 *
 * These live in this browser profile only. Deletion is permanent because there is no server copy -
 * the confirmation dialog says so rather than implying an undo exists.
 */
export function ScanLibrary() {
  const library = useScanLibrary();
  const quarantined = useQuarantinedScans();
  const deleteScan = useDeleteScan();
  const [pendingDelete, setPendingDelete] = useState<ScanRecord | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DatabaseIcon className="size-4" aria-hidden="true" />
          Stored scans
        </CardTitle>
        <CardDescription>
          Saved in this browser and kept across restarts. Nothing is uploaded or synced.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {library.isLoading && <Skeleton className="h-16 w-full" />}

        {library.isError && (
          <p className="text-sm text-destructive">
            Local storage could not be read. Scans from this session may not be listed.
          </p>
        )}

        {library.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No scans stored yet. Analyze a URL and the result will be kept here.
          </p>
        )}

        <ul className="divide-y divide-border">
          {library.data?.map((record) => (
            <li key={record.id} className="flex items-center gap-3 py-2.5">
              <div className="min-w-0 flex-1">
                <Link
                  to={`/scan/${record.id}`}
                  className="flex items-baseline gap-2 font-medium hover:underline"
                >
                  <span className="truncate">{record.host}</span>
                  <span className="truncate font-mono text-xs text-muted-foreground">
                    {truncateMiddle(record.final_url ?? record.normalized_url, 56)}
                  </span>
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>{formatRelativeTime(record.created_at)}</span>
                  <span className="font-mono">{record.finding_count} findings</span>
                  <span className="font-mono">{formatBytes(record.result_bytes)}</span>
                  <span className="font-mono">engine {record.engine_version}</span>
                  {record.error_count > 0 && (
                    <Badge variant="attention">{record.error_count} issues</Badge>
                  )}
                  {record.security_percentage !== null && (
                    <Badge variant="outline">posture {record.security_percentage}%</Badge>
                  )}
                </div>
                <div className="mt-1.5 flex items-center gap-1.5" aria-hidden="true">
                  {SECTION_KEYS.map((key) => (
                    <StatusDot key={key} status={record.section_statuses[key] ?? 'unavailable'} />
                  ))}
                </div>
              </div>

              <Button variant="ghost" size="icon" asChild aria-label={`Open scan of ${record.host}`}>
                <Link to={`/scan/${record.id}`}>
                  <ArrowRightIcon className="size-4" />
                </Link>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Delete scan of ${record.host}`}
                onClick={() => setPendingDelete(record)}
              >
                <Trash2Icon className="size-4" />
              </Button>
            </li>
          ))}
        </ul>

        {quarantined.data && quarantined.data.length > 0 && (
          <div className="rounded-md border border-status-attention/40 bg-status-attention/5 p-3 text-xs">
            <p className="font-medium">
              {quarantined.data.length} stored scan(s) cannot be displayed
            </p>
            <ul className="mt-1 space-y-1 text-muted-foreground">
              {quarantined.data.map((item) => (
                <li key={item.id} className="flex items-center gap-2">
                  <code className="font-mono">{item.id}</code>
                  <span className="flex-1">{item.reason}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => deleteScan.mutate(item.id)}
                    className="h-6"
                  >
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>

      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this scan?</DialogTitle>
            <DialogDescription>
              The analysis of <span className="font-mono">{pendingDelete?.host}</span> and its
              screenshots will be removed from this browser. There is no server copy, so this cannot
              be undone. Download the report first if you need to keep it.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={() => {
                if (pendingDelete) deleteScan.mutate(pendingDelete.id);
                setPendingDelete(null);
              }}
            >
              Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
