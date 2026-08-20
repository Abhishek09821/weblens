/**
 * Executive overview — the first thing a user sees after a scan completes.
 *
 * Every value shown here is derived from the structured analysis result.
 * Nothing is invented. Inferences are labelled.
 */
import { ExternalLinkIcon, ShieldCheckIcon, ZapIcon, EyeIcon, CodeIcon, PaletteIcon, GlobeIcon, SparklesIcon } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api/client';
import { buildOverview } from '@/lib/presentation/overview';
import { formatBytes, formatDuration } from '@/lib/format/values';
import type { AnalysisResult } from '@/types/analysis';

export function OverviewPanel({ result }: { result: AnalysisResult }) {
  const overview = buildOverview(result);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(false);

  const requestAiSummary = async () => {
    setAiLoading(true);
    setAiError(false);
    try {
      const response = await api.summarize(result);
      if (response.available && response.summary) {
        setAiSummary(response.summary);
      } else {
        setAiError(true);
      }
    } catch {
      setAiError(true);
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* AI Summary */}
      {!aiSummary && (
        <Card className="border-dashed border-primary/30">
          <CardContent className="flex items-center justify-between py-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <SparklesIcon className="size-4 text-primary" />
              <span>Get an AI-powered summary of this analysis</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void requestAiSummary()}
              disabled={aiLoading}
            >
              {aiLoading ? 'Generating...' : 'Generate Summary'}
            </Button>
          </CardContent>
          {aiError && (
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">
                AI summary unavailable. Set GROQ_API_KEY on the backend to enable. The analysis is complete without it.
              </p>
            </CardContent>
          )}
        </Card>
      )}

      {aiSummary && (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <SparklesIcon className="size-4 text-primary" />
              AI Summary
              <Badge variant="muted" className="text-[10px]">AI-generated from verified findings</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="whitespace-pre-wrap text-sm text-foreground/90">
              {aiSummary}
            </div>
            <p className="mt-3 text-[10px] text-muted-foreground">
              Generated from verified analysis data only. Does not introduce new detections.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Target */}
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Website Overview</h2>
        <a
          href={overview.target.url}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-1 inline-flex items-center gap-1 font-mono text-sm text-muted-foreground hover:text-foreground"
        >
          {overview.target.url}
          <ExternalLinkIcon className="size-3" />
        </a>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Technology */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CodeIcon className="size-4 text-primary" />
              Technology
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overview.technology.status === 'unavailable' ? (
              <p className="text-sm text-muted-foreground">Unable to verify</p>
            ) : overview.technology.detected.length === 0 ? (
              <p className="text-sm text-muted-foreground">No technologies detected from observable signals</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {overview.technology.detected.map((tech) => (
                  <Badge key={tech} variant="outline">{tech}</Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Rendering */}
        {overview.rendering.strategy && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <GlobeIcon className="size-4 text-primary" />
                Rendering
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm capitalize">
                {overview.rendering.certainty === 'Inferred' && (
                  <span className="text-muted-foreground">Likely </span>
                )}
                {overview.rendering.strategy}
              </p>
              <Badge variant="muted" className="mt-1">{overview.rendering.certainty}</Badge>
            </CardContent>
          </Card>
        )}

        {/* Security */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ShieldCheckIcon className="size-4 text-primary" />
              Security Posture
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overview.security.percentage !== null ? (
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-2xl font-semibold tabular-nums">
                    {overview.security.percentage}%
                  </span>
                  <Badge variant="outline">{overview.security.bandPhrase}</Badge>
                </div>
                <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${Math.min(overview.security.percentage, 100)}%` }}
                  />
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Score not available</p>
            )}
          </CardContent>
        </Card>

        {/* Performance */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ZapIcon className="size-4 text-primary" />
              Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {overview.performance.ttfb !== null && (
                <MetricCell label="TTFB" value={formatDuration(overview.performance.ttfb)} />
              )}
              {overview.performance.fcp !== null && (
                <MetricCell label="FCP" value={formatDuration(overview.performance.fcp)} />
              )}
              {overview.performance.transferBytes !== null && (
                <MetricCell label="Transfer" value={formatBytes(overview.performance.transferBytes)} />
              )}
              {overview.performance.requestCount !== null && (
                <MetricCell label="Requests" value={`${overview.performance.requestCount}`} />
              )}
            </div>
            {overview.performance.ttfb === null && (
              <p className="text-sm text-muted-foreground">Not measured in this scan</p>
            )}
          </CardContent>
        </Card>

        {/* Design */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <PaletteIcon className="size-4 text-primary" />
              Design
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overview.design.observations.length > 0 ? (
              <div className="space-y-1.5">
                {overview.design.fonts.length > 0 && (
                  <p className="text-sm">{overview.design.fonts.slice(0, 3).join(', ')}</p>
                )}
                <div className="flex flex-wrap gap-1">
                  {overview.design.observations.map((obs) => (
                    <Badge key={obs} variant="muted" className="text-xs">{obs}</Badge>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Design analysis not available</p>
            )}
          </CardContent>
        </Card>

        {/* Accessibility */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <EyeIcon className="size-4 text-primary" />
              Accessibility
            </CardTitle>
          </CardHeader>
          <CardContent>
            {overview.accessibility.issues.length > 0 ? (
              <ul className="space-y-1 text-sm">
                {overview.accessibility.issues.map((issue) => (
                  <li key={issue} className="text-muted-foreground">• {issue}</li>
                ))}
              </ul>
            ) : overview.accessibility.violationCount !== null ? (
              <p className="text-sm">
                {overview.accessibility.violationCount === 0
                  ? 'No automated violations detected'
                  : `${overview.accessibility.violationCount} automated rule violations`}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">Not assessed in this scan</p>
            )}
          </CardContent>
        </Card>

        {/* Infrastructure */}
        {(overview.infrastructure.platforms.length > 0 ||
          overview.infrastructure.cdn.length > 0 ||
          overview.infrastructure.server.length > 0) && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                <GlobeIcon className="size-4 text-primary" />
                Infrastructure
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1.5">
                {[...overview.infrastructure.platforms,
                  ...overview.infrastructure.cdn,
                  ...overview.infrastructure.server,
                ].map((item) => (
                  <Badge key={item} variant="outline">{item}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-xs text-muted-foreground">{label}</span>
      <p className="font-mono text-sm font-medium">{value}</p>
    </div>
  );
}
