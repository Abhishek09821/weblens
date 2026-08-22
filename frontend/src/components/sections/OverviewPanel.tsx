/** Focused V2 overview with evidence quality gate and AI intelligence fallback. */
import { useState } from 'react';
import {
  ActivityIcon,
  BrainCircuitIcon,
  CodeIcon,
  ExternalLinkIcon,
  GaugeIcon,
  PaletteIcon,
  ShieldCheckIcon,
  SparklesIcon,
} from 'lucide-react';

import { FindingStatusBadge } from '@/components/sections/StatusBadge';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api/client';
import { buildOverview } from '@/lib/presentation/overview';
import type { AnalysisResult, EvidenceQuality, SectionKey } from '@/types/analysis';

export function OverviewPanel({ result }: { result: AnalysisResult }) {
  const overview = buildOverview(result);
  const quality = result.quality;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold tracking-tight">{overview.target.host}</h2>
          <Badge variant="outline">{overview.target.scanStatus.replace(/_/g, ' ')}</Badge>
          {overview.target.httpStatus !== null && (
            <Badge variant="muted" className="font-mono">
              HTTP {overview.target.httpStatus}
            </Badge>
          )}
        </div>
        <a
          href={overview.target.url}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-1 inline-flex items-center gap-1 break-all font-mono text-sm text-muted-foreground hover:text-foreground"
        >
          {overview.target.url}
          <ExternalLinkIcon className="size-3 shrink-0" aria-hidden="true" />
        </a>
      </div>

      {/* Evidence Quality Gate */}
      {quality && (
        <EvidenceQualityCard quality={quality} scanId={result.scan.scan_id} />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CodeIcon className="size-4 text-primary" aria-hidden="true" />
              Tech Stack
            </CardTitle>
            {overview.technology.rendering && (
              <CardDescription className="flex flex-wrap items-center gap-2">
                Rendering: {overview.technology.rendering.value}
                <FindingStatusBadge status={overview.technology.rendering.status} />
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {overview.technology.unavailable ? (
              <p className="text-sm text-muted-foreground">Technology evidence was unavailable.</p>
            ) : overview.technology.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No technologies were identified from observable signals.
              </p>
            ) : (
              <ul className="space-y-2">
                {overview.technology.items.map((item) => (
                  <li key={`${item.name}-${item.status}`} className="flex items-center justify-between gap-2 text-sm">
                    <span>{item.name}</span>
                    <FindingStatusBadge status={item.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <PaletteIcon className="size-4 text-primary" aria-hidden="true" />
              Design
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {overview.design.unavailable ? (
              <p className="text-sm text-muted-foreground">Design evidence was unavailable.</p>
            ) : (
              <>
                {overview.design.fonts.length > 0 && (
                  <p className="text-sm">Fonts: {overview.design.fonts.join(', ')}</p>
                )}
                {overview.design.colorsObserved !== null && (
                  <p className="text-sm">{overview.design.colorsObserved} background colors observed</p>
                )}
                {overview.design.observations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {overview.design.observations.map((observation) => (
                      <Badge key={observation} variant="muted">
                        {observation}
                      </Badge>
                    ))}
                  </div>
                )}
                {overview.design.fonts.length === 0 &&
                  overview.design.colorsObserved === null &&
                  overview.design.observations.length === 0 && (
                    <p className="text-sm text-muted-foreground">No design values were observed.</p>
                  )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ShieldCheckIcon className="size-4 text-primary" aria-hidden="true" />
              Security Posture
            </CardTitle>
            <CardDescription>Passive external observations, not proof that the site is secure.</CardDescription>
          </CardHeader>
          <CardContent>
            {overview.security.percentage === null ? (
              <p className="text-sm text-muted-foreground">A posture score was not available.</p>
            ) : (
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-mono text-2xl font-semibold tabular-nums">
                  {overview.security.percentage}%
                </span>
                {overview.security.bandPhrase && (
                  <Badge variant="outline">{overview.security.bandPhrase}</Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <ActivityIcon className="size-4 text-primary" aria-hidden="true" />
              Traffic & Popularity
            </CardTitle>
            <CardDescription>
              Provider: {overview.traffic.providerName ?? 'none configured'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {overview.traffic.estimates.length > 0 ? (
              <ul className="space-y-2">
                {overview.traffic.estimates.map((estimate) => (
                  <li key={estimate.name} className="flex items-center justify-between gap-3 text-sm">
                    <span>
                      {estimate.name}: <strong>{estimate.value}</strong>
                    </span>
                    <FindingStatusBadge status={estimate.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">
                {overview.traffic.unavailableReason}
              </p>
            )}
            {overview.traffic.analyticsServices.length > 0 && (
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Observed analytics signals</p>
                <div className="flex flex-wrap gap-1.5">
                  {overview.traffic.analyticsServices.map((service) => (
                    <Badge key={service} variant="outline">{service}</Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="sm:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <GaugeIcon className="size-4 text-primary" aria-hidden="true" />
              Evidence Summary
            </CardTitle>
            <CardDescription>
              {overview.evidence.analyzersCompleted}/{overview.evidence.analyzersTotal} analyzers completed
              {overview.evidence.errorCount > 0 && ` · ${overview.evidence.errorCount} scan issues`}
              {overview.evidence.limitationCount > 0 && ` · ${overview.evidence.limitationCount} stated limitations`}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            <EvidenceCount label="Verified" value={overview.evidence.verified} />
            <EvidenceCount label="Strongly inferred" value={overview.evidence.stronglyInferred} />
            <EvidenceCount label="Inferred" value={overview.evidence.inferred} />
            <EvidenceCount label="AI hypotheses" value={overview.evidence.aiInferred} />
            <EvidenceCount label="Negative / unknown" value={overview.evidence.unknown} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/** Evidence quality gate card with AI fallback button */
function EvidenceQualityCard({
  quality,
  scanId,
}: {
  quality: NonNullable<AnalysisResult['quality']>;
  scanId: string;
}) {
  const [isRunning, setIsRunning] = useState(false);
  const [aiResult, setAiResult] = useState<string | null>(null);

  const handleRunIntelligence = async () => {
    setIsRunning(true);
    setAiResult(null);
    try {
      const response = await api.runIntelligence(scanId, {
        sections: quality.ai_fallback_sections as SectionKey[],
      });
      setAiResult(
        `AI intelligence completed. ${response.findings_added} findings added to ${response.sections_enhanced.join(', ')}.`
      );
    } catch {
      setAiResult('AI intelligence failed. The normal scan result is still available.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <Card className={quality.ai_fallback_available ? 'border-amber-200 dark:border-amber-800' : ''}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <BrainCircuitIcon className="size-4 text-primary" aria-hidden="true" />
          Evidence Quality
          <QualityBadge quality={quality.overall} />
        </CardTitle>
        <CardDescription>
          Overall score: {quality.overall_score}/100
          {quality.ai_fallback_available && ' · AI intelligence available'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Per-section quality */}
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.values(quality.sections).map((sq) => (
            <div key={sq.section} className="flex items-center justify-between gap-2 text-sm">
              <span className="capitalize">{sq.section}</span>
              <div className="flex items-center gap-1.5">
                <QualityBadge quality={sq.quality} />
                <span className="font-mono text-xs text-muted-foreground">{sq.score}</span>
              </div>
            </div>
          ))}
        </div>

        {/* AI fallback option */}
        {quality.ai_fallback_available && !aiResult && (
          <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
            <p className="text-sm font-medium">Evidence collection was incomplete.</p>
            <p className="text-xs text-muted-foreground">
              WebLens can research public information about this website and produce
              evidence-backed technology, design, security and traffic verdicts.
              AI-generated conclusions will be clearly marked.
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={isRunning}
              onClick={handleRunIntelligence}
              className="gap-1.5"
            >
              <SparklesIcon className="size-3.5" aria-hidden="true" />
              {isRunning ? 'Running AI Intelligence...' : 'Run AI Intelligence'}
            </Button>
            {quality.ai_fallback_sections.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Recommended for: {quality.ai_fallback_sections.join(', ')}
              </p>
            )}
          </div>
        )}

        {/* AI result feedback */}
        {aiResult && (
          <div className="rounded-md border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950/30">
            <p className="text-sm">{aiResult}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Reload the page to see updated findings in section views and reports.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function QualityBadge({ quality }: { quality: EvidenceQuality }) {
  const variants: Record<EvidenceQuality, 'verified' | 'inferred' | 'attention' | 'muted'> = {
    high: 'verified',
    medium: 'inferred',
    low: 'attention',
    failed: 'muted',
  };
  return (
    <Badge variant={variants[quality]} className="text-[10px]">
      {quality.toUpperCase()}
    </Badge>
  );
}

function EvidenceCount({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span className="font-mono font-semibold tabular-nums">{value}</span>{' '}
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}
