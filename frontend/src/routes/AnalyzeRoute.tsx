import { CircleAlertIcon, TriangleAlertIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { ScanLibrary } from '@/components/history/ScanLibrary';
import { ScanProgress } from '@/components/scan/ScanProgress';
import { UrlForm } from '@/components/scan/UrlForm';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useCapabilities, useHealth } from '@/features/scan/useHealth';
import { useScanRunner } from '@/features/scan/useScanRunner';
import { isBusy } from '@/features/scan/types';

export function AnalyzeRoute() {
  const navigate = useNavigate();
  const runner = useScanRunner((scanId) => navigate(`/scan/${scanId}`));
  const health = useHealth();
  const capabilities = useCapabilities();

  const busy = isBusy(runner.phase);
  const implemented = capabilities.data?.analyzers.filter((entry) => entry.implemented) ?? [];
  const planned = capabilities.data?.analyzers.filter((entry) => !entry.implemented) ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">Website technical intelligence</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Enter a public URL. WebLens collects observable evidence from the page and reports what
            can be established from it — and says so plainly when something cannot.
          </p>
        </header>

        <Card>
          <CardContent className="pt-4">
            <UrlForm
              onSubmit={(url) => void runner.start(url)}
              disabled={busy}
              {...(runner.phase.kind === 'invalid' ? { externalError: runner.phase.message } : {})}
            />
          </CardContent>
        </Card>

        {health.isError && (
          <Alert variant="destructive">
            <CircleAlertIcon className="size-4" />
            <AlertTitle>The WebLens backend is not reachable</AlertTitle>
            <AlertDescription>
              Start it with <code className="font-mono">make dev-backend</code> and it will be
              available on http://127.0.0.1:8000. Stored scans remain readable without it.
            </AlertDescription>
          </Alert>
        )}

        {health.data && !health.data.browser.available && (
          <Alert variant="warning">
            <TriangleAlertIcon className="size-4" />
            <AlertTitle>Browser collection is unavailable</AlertTitle>
            <AlertDescription>
              {health.data.browser.detail ??
                'Playwright has no browser installed, so only HTTP-based evidence can be collected.'}{' '}
              Sections that need a rendered page will report that they could not be produced.
            </AlertDescription>
          </Alert>
        )}

        {(runner.phase.kind === 'running' || runner.phase.kind === 'submitting') && (
          <ScanProgress
            job={runner.phase.kind === 'running' ? runner.phase.job : null}
            elapsedMs={runner.elapsedMs}
            url={runner.phase.kind === 'submitting' ? runner.phase.url : (runner.phase.job?.requested_url ?? '')}
          />
        )}

        {runner.phase.kind === 'persisting' && (
          <Alert variant="info">
            <AlertTitle>Storing the result in this browser</AlertTitle>
            <AlertDescription>
              The backend releases its copy once the scan is saved locally.
            </AlertDescription>
          </Alert>
        )}

        {runner.phase.kind === 'failed' && (
          <Alert variant="destructive">
            <CircleAlertIcon className="size-4" />
            <AlertTitle>{runner.phase.title}</AlertTitle>
            <AlertDescription className="space-y-2">
              <p>{runner.phase.detail}</p>
              {runner.phase.problem?.code && (
                <p className="font-mono text-xs">{runner.phase.problem.code}</p>
              )}
              <Button variant="outline" size="sm" onClick={runner.reset}>
                Dismiss
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <ScanLibrary />
      </div>

      <aside className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>What this build analyzes</CardTitle>
            <CardDescription>
              Reported from the backend rather than assumed, so nothing is presented as examined when
              it was not.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {capabilities.isLoading && <p className="text-muted-foreground">Loading…</p>}
            {capabilities.data && (
              <>
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Implemented ({implemented.length})
                  </p>
                  <ul className="space-y-1">
                    {implemented.map((entry) => (
                      <li key={entry.id} className="flex items-start gap-2">
                        <Badge variant="verified" className="mt-0.5 font-mono">
                          {entry.id}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Declared, not yet built ({planned.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {planned.map((entry) => (
                      <Badge key={entry.id} variant="muted" className="font-mono" title={entry.description}>
                        {entry.id}
                      </Badge>
                    ))}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Collection mode:{' '}
                  <code className="font-mono">{capabilities.data.collection_mode}</code>
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>How to read results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs text-muted-foreground">
            <p>
              <strong className="text-foreground">Verified</strong> claims are backed by evidence you
              can inspect. <strong className="text-foreground">Inferred</strong> claims come from
              indirect signals, which are shown alongside.
            </p>
            <p>
              <strong className="text-foreground">Not detected</strong> means the signal was absent
              from the evidence — not that the technology is unused.
            </p>
            <p>Security is the only section with a score, and its rules are published.</p>
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}
