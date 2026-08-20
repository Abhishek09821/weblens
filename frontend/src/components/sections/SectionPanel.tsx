import { DownloadIcon, TriangleAlertIcon } from 'lucide-react';

import { AccessibilityDetails } from '@/components/sections/AccessibilityDetails';
import { DesignDetails } from '@/components/sections/DesignDetails';
import { FindingsTable } from '@/components/sections/FindingsTable';
import { InterpretationCallout } from '@/components/sections/InterpretationCallout';
import { PerformanceDetails } from '@/components/sections/PerformanceDetails';
import { SectionStatusBadge } from '@/components/sections/StatusBadge';
import { SecurityDetails } from '@/components/sections/SecurityDetails';
import { SeoDetails } from '@/components/sections/SeoDetails';
import { TechnologyDetails } from '@/components/sections/TechnologyDetails';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { downloadText } from '@/features/reports/bundle';
import { renderSectionReport } from '@/features/reports/generate';
import { sectionLabel, sectionSummary } from '@/lib/format/labels';
import { formatDuration } from '@/lib/format/values';
import { sectionIsRenderable } from '@/lib/format/status';
import type { AnalysisResult, SectionKey } from '@/types/analysis';

export function SectionPanel({
  result,
  sectionKey,
}: {
  result: AnalysisResult;
  sectionKey: SectionKey;
}) {
  const section = result.sections[sectionKey];
  const renderable = sectionIsRenderable(section.meta.status);
  const reportFile = renderSectionReport(result, sectionKey);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight">{sectionLabel(sectionKey)}</h2>
            <SectionStatusBadge status={section.meta.status} />
          </div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {sectionSummary(sectionKey)}
          </p>
        </div>
        {reportFile && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => downloadText(reportFile)}
            title={`Download ${reportFile.path}`}
          >
            <DownloadIcon className="size-3.5" />
            {reportFile.path}
          </Button>
        )}
      </div>

      {!renderable && (
        <Alert variant={section.meta.status === 'unavailable' ? 'warning' : 'default'}>
          <TriangleAlertIcon className="size-4" />
          <AlertTitle>
            {section.meta.status === 'not_implemented'
              ? 'Not implemented in this build'
              : 'No findings available'}
          </AlertTitle>
          <AlertDescription>
            {section.meta.unavailable_reason ??
              'This section could not be produced for this scan.'}
            {section.meta.status === 'not_implemented' && (
              <span className="mt-1 block">
                Nothing about the target was inferred in its place.
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}

      {sectionKey === 'security' && renderable && <SecurityDetails section={section} />}
      {sectionKey === 'seo' && renderable && <SeoDetails section={section} />}
      {sectionKey === 'technology' && renderable && <TechnologyDetails result={result} />}
      {sectionKey === 'design' && renderable && <DesignDetails result={result} />}
      {sectionKey === 'performance' && renderable && <PerformanceDetails result={result} />}
      {sectionKey === 'accessibility' && renderable && <AccessibilityDetails result={result} />}

      {renderable && (
        <details className="rounded-lg border border-border">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">
            All Findings ({section.findings.length}) — Technical Detail
          </summary>
          <div className="border-t border-border px-4 py-3">
            <FindingsTable findings={section.findings} />
          </div>
        </details>
      )}
      {renderable && <InterpretationCallout interpretations={section.interpretations} />}

      <AnalyzerRunTable section={section} />

      {section.meta.limitations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Limitations</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
              {section.meta.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/**
 * Which analyzers ran, and which exist but did not.
 *
 * This is the difference between "this site has no framework signals" and "framework detection is
 * not built yet" - a distinction the user cannot infer from an empty panel.
 */
function AnalyzerRunTable({ section }: { section: AnalysisResult['sections'][SectionKey] }) {
  if (section.meta.analyzers.length === 0) return null;

  return (
    <details className="rounded-lg border border-border">
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium">
        Analyzers ({section.meta.analyzers.filter((run) => run.status === 'completed').length}/
        {section.meta.analyzers.length} completed)
      </summary>
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
              <th scope="col" className="px-3 py-2 font-medium">Analyzer</th>
              <th scope="col" className="px-3 py-2 font-medium">Version</th>
              <th scope="col" className="px-3 py-2 font-medium">Outcome</th>
              <th scope="col" className="px-3 py-2 font-medium">Duration</th>
              <th scope="col" className="px-3 py-2 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {section.meta.analyzers.map((run) => (
              <tr key={run.id} className="border-b border-border/60 last:border-0">
                <td className="px-3 py-1.5 font-mono text-xs">{run.id}</td>
                <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">{run.version}</td>
                <td className="px-3 py-1.5 text-xs">{run.status.replace(/_/g, ' ')}</td>
                <td className="px-3 py-1.5 text-xs text-muted-foreground">
                  {formatDuration(run.duration_ms)}
                </td>
                <td className="px-3 py-1.5 text-xs text-muted-foreground">
                  {run.error_detail ?? run.missing_evidence.join(', ') ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
