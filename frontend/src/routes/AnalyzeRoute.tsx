import {
  ArrowUpRightIcon,
  CircleAlertIcon,
  DatabaseIcon,
  EyeIcon,
  FileCheck2Icon,
  Globe2Icon,
  LockKeyholeIcon,
  RadarIcon,
  TriangleAlertIcon,
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

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

const PRINCIPLES = [
  {
    icon: EyeIcon,
    label: 'Inspectable evidence',
    detail: 'Every claim keeps a trail back to the response, page, or browser signal behind it.',
  },
  {
    icon: FileCheck2Icon,
    label: 'Deterministic detection',
    detail: 'Facts come from explicit analyzers—not an AI model filling gaps with plausible answers.',
  },
  {
    icon: LockKeyholeIcon,
    label: 'Local by default',
    detail: 'Completed reports live in this browser. The backend releases its temporary copy.',
  },
] as const;

export function AnalyzeRoute() {
  const navigate = useNavigate();
  const runner = useScanRunner((scanId) => navigate(`/scan/${scanId}`));
  const health = useHealth();
  const capabilities = useCapabilities();

  const busy = isBusy(runner.phase);
  const implemented = capabilities.data?.analyzers.filter((entry) => entry.implemented) ?? [];
  const planned = capabilities.data?.analyzers.filter((entry) => !entry.implemented) ?? [];
  const collectorStatus = health.isError
    ? 'Backend offline'
    : health.isLoading
      ? 'Connecting…'
      : health.data?.browser.available
        ? 'Browser collector ready'
        : 'HTTP collector ready';

  return (
    <div className="space-y-8 pb-8">
      <section
        aria-labelledby="landing-title"
        className="landing-hero relative isolate overflow-hidden rounded-[1.75rem] border border-border px-5 py-8 shadow-sm sm:px-8 sm:py-12 lg:px-12 lg:py-14"
      >
        <div className="relative z-10 grid items-center gap-10 lg:grid-cols-[minmax(0,1.25fr)_minmax(20rem,0.75fr)] lg:gap-14">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border/80 bg-background/70 px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-xs backdrop-blur">
              <RadarIcon className="size-3.5 text-primary" aria-hidden="true" />
              Evidence-led website analysis
            </div>

            <h1
              id="landing-title"
              className="max-w-3xl text-4xl leading-[0.98] font-semibold tracking-[-0.045em] text-balance sm:text-5xl lg:text-6xl xl:text-7xl"
            >
              See what a website{' '}
              <span className="font-serif font-normal italic text-primary">reveals.</span>
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              WebLens observes a public page through a real browser, verifies the signals it finds,
              and turns them into a technical report you can inspect—not a black-box score.
            </p>

            <div className="mt-8 max-w-2xl rounded-2xl border border-border/80 bg-background/80 p-3 shadow-[0_20px_70px_-35px_var(--primary)] backdrop-blur sm:p-4">
              <UrlForm
                prominent
                onSubmit={(url) => void runner.start(url)}
                disabled={busy}
                {...(runner.phase.kind === 'invalid'
                  ? { externalError: runner.phase.message }
                  : {})}
              />
            </div>

            <dl className="mt-7 flex flex-wrap gap-x-8 gap-y-3 text-xs">
              <div className="flex items-center gap-2">
                <dt className="font-mono font-semibold text-foreground">01</dt>
                <dd className="text-muted-foreground">One public URL</dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="font-mono font-semibold text-foreground">Local</dt>
                <dd className="text-muted-foreground">Browser storage</dd>
              </div>
              <div className="flex items-center gap-2">
                <dt className="font-mono font-semibold text-foreground">Passive</dt>
                <dd className="text-muted-foreground">By design</dd>
              </div>
            </dl>
          </div>

          <div className="relative mx-auto w-full max-w-md">
            <div
              className="absolute top-1/2 left-1/2 size-72 -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary/10 sm:size-96"
              aria-hidden="true"
            />
            <div
              className="absolute top-1/2 left-1/2 size-52 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-primary/20 sm:size-72"
              aria-hidden="true"
            />

            <Card className="relative overflow-hidden border-border/80 bg-card/85 shadow-xl shadow-foreground/5 backdrop-blur">
              <div className="flex items-center justify-between border-b border-border/80 px-5 py-4">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`size-2 rounded-full ${health.isError ? 'bg-status-attention' : 'bg-status-verified'}`}
                    aria-hidden="true"
                  />
                  <span className="text-sm font-medium">{collectorStatus}</span>
                </div>
                <span className="font-mono text-[10px] tracking-widest text-muted-foreground uppercase">
                  Collection pipeline
                </span>
              </div>

              <CardContent className="p-5">
                <ol className="space-y-1">
                  <PipelineStep
                    number="01"
                    icon={Globe2Icon}
                    title="Observe"
                    detail="HTTP, TLS, DNS, and a rendered page"
                  />
                  <PipelineStep
                    number="02"
                    icon={RadarIcon}
                    title="Verify"
                    detail="Deterministic analyzers check the evidence"
                  />
                  <PipelineStep
                    number="03"
                    icon={DatabaseIcon}
                    title="Preserve"
                    detail="The report is saved in your browser"
                    last
                  />
                </ol>

                <div className="mt-5 grid grid-cols-2 gap-3 border-t border-border/80 pt-4">
                  <div>
                    <p className="font-mono text-xl font-semibold">
                      {capabilities.data ? implemented.length : '—'}
                    </p>
                    <p className="text-xs text-muted-foreground">Analyzers available</p>
                  </div>
                  <div>
                    <p className="font-mono text-xl font-semibold">
                      {capabilities.data?.collection_mode ?? '—'}
                    </p>
                    <p className="text-xs text-muted-foreground">Collection mode</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <div className="space-y-4" aria-live="polite">
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
            url={
              runner.phase.kind === 'submitting'
                ? runner.phase.url
                : (runner.phase.job?.requested_url ?? '')
            }
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
      </div>

      <section aria-labelledby="principles-title" className="py-4 sm:py-8">
        <div className="grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
          <div>
            <p className="mb-3 font-mono text-xs font-semibold tracking-[0.16em] text-primary uppercase">
              Built for clarity
            </p>
            <h2
              id="principles-title"
              className="max-w-md text-3xl leading-tight font-semibold tracking-[-0.035em] text-balance sm:text-4xl"
            >
              A technical report that shows its work.
            </h2>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-muted-foreground">
              Detection is useful only when you can understand where it came from. WebLens keeps
              evidence and uncertainty visible from collection through export.
            </p>
            <Button variant="link" className="mt-3 h-auto px-0" asChild>
              <Link to="/about">
                Read the methodology
                <ArrowUpRightIcon className="size-3.5" />
              </Link>
            </Button>
          </div>

          <div className="grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3">
            {PRINCIPLES.map(({ icon: Icon, label, detail }) => (
              <article key={label} className="bg-card p-5 sm:min-h-52 sm:p-6">
                <div className="mb-10 flex size-10 items-center justify-center rounded-full border border-border bg-background text-primary sm:mb-14">
                  <Icon className="size-4" aria-hidden="true" />
                </div>
                <h3 className="text-sm font-semibold">{label}</h3>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_23rem]">
        <ScanLibrary />

        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Available in this build</CardTitle>
              <CardDescription>
                Reported live by the backend, so planned work is never presented as examined.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {capabilities.isLoading && <p className="text-muted-foreground">Loading…</p>}
              {capabilities.data && (
                <>
                  <div>
                    <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                      Implemented ({implemented.length})
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {implemented.map((entry) => (
                        <Badge
                          key={entry.id}
                          variant="verified"
                          className="font-mono text-foreground"
                        >                          {entry.id}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {planned.length > 0 && (
                    <details className="group rounded-md border border-border px-3 py-2">
                      <summary className="cursor-pointer text-xs font-medium text-muted-foreground marker:text-primary">
                        Declared, not yet built ({planned.length})
                      </summary>
                      <div className="mt-3 flex flex-wrap gap-1">
                        {planned.map((entry) => (
                          <Badge
                            key={entry.id}
                            variant="muted"
                            className="font-mono"
                            title={entry.description}
                          >
                            {entry.id}
                          </Badge>
                        ))}
                      </div>
                    </details>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Read findings precisely</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-xs leading-relaxed text-muted-foreground">
              <p>
                <strong className="text-foreground">Verified</strong> claims are backed by evidence
                you can inspect. <strong className="text-foreground">Inferred</strong> claims come
                from indirect signals shown alongside them.
              </p>
              <p>
                <strong className="text-foreground">Not detected</strong> means a signal was absent
                from the collected evidence—not that the technology is unused.
              </p>
              <p>Security is the only section with a score, and its rules are published.</p>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function PipelineStep({
  number,
  icon: Icon,
  title,
  detail,
  last = false,
}: {
  number: string;
  icon: typeof Globe2Icon;
  title: string;
  detail: string;
  last?: boolean;
}) {
  return (
    <li className="grid grid-cols-[2rem_1fr] gap-3">
      <div className="flex flex-col items-center">
        <div className="flex size-8 items-center justify-center rounded-full border border-border bg-background text-primary shadow-xs">
          <Icon className="size-3.5" aria-hidden="true" />
        </div>
        {!last && <div className="my-1 h-8 w-px bg-border" aria-hidden="true" />}
      </div>
      <div className="pt-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          {title}
          <span className="font-mono text-[10px] text-muted-foreground">{number}</span>
        </p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
      </div>
    </li>
  );
}
