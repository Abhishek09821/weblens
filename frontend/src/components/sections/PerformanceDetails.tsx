/**
 * Performance — human-readable metrics with explanations.
 *
 * Key measurements shown prominently with visual metric cards.
 * Resource breakdown in a clear table.
 * Limitations stated plainly.
 */
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatBytes, formatDuration } from '@/lib/format/values';
import type { AnalysisResult, Finding } from '@/types/analysis';

export function PerformanceDetails({ result }: { result: AnalysisResult }) {
  const findings = result.sections.performance.findings;

  const ttfb = findValue(findings, 'performance.timings:ttfb');
  const fcp = findValue(findings, 'performance.timings:fcp');
  const lcp = findValue(findings, 'performance.timings:lcp');
  const cls = findValue(findings, 'performance.timings:cls');
  const dcl = findValue(findings, 'performance.timings:dcl');
  const load = findValue(findings, 'performance.timings:load');
  const tbt = findValue(findings, 'performance.timings:tbt');
  const requestCount = findValue(findings, 'performance.resources:request-count');
  const transferSize = findValue(findings, 'performance.resources:transfer-size');
  const resourceTypes = findings.find((f) => f.id === 'performance.resources:resource-types');
  const failedRequests = findings.find((f) => f.id === 'performance.resources:failed-requests');

  return (
    <div className="space-y-5">
      {/* Key Metrics */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Key Measurements</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {ttfb !== null && <MetricCard label="Time to First Byte" value={formatDuration(ttfb)} explanation="How quickly the server begins responding" />}
            {fcp !== null && <MetricCard label="First Contentful Paint" value={formatDuration(fcp)} explanation="When the first content appears" />}
            {lcp !== null && <MetricCard label="Largest Contentful Paint" value={formatDuration(lcp)} explanation="When the main content finishes loading" />}
            {cls !== null && <MetricCard label="Layout Shift" value={String(cls)} explanation="Visual stability (lower is better)" />}
            {dcl !== null && <MetricCard label="DOM Content Loaded" value={formatDuration(dcl)} explanation="When HTML is fully parsed" />}
            {load !== null && <MetricCard label="Load Event" value={formatDuration(load)} explanation="When all resources finish loading" />}
            {tbt !== null && <MetricCard label="Blocking Time" value={formatDuration(tbt)} explanation="Total time the main thread was blocked" />}
            {requestCount !== null && <MetricCard label="Network Requests" value={String(requestCount)} explanation="Total HTTP requests made" />}
            {transferSize !== null && <MetricCard label="Transfer Size" value={formatBytes(transferSize)} explanation="Total data downloaded" />}
          </div>
        </CardContent>
      </Card>

      {/* Resource Breakdown */}
      {resourceTypes && resourceTypes.values.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Resource Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {resourceTypes.values.map((entry) => {
                const [type, count] = entry.split(': ');
                return (
                  <div key={entry} className="flex items-center justify-between text-sm">
                    <span className="capitalize">{type}</span>
                    <span className="font-mono text-muted-foreground">{count}</span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Failed Requests */}
      {failedRequests && typeof failedRequests.value === 'number' && failedRequests.value > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              Failed Resources
              <Badge variant="attention">{failedRequests.value}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {failedRequests.values.length > 0 && (
              <ul className="space-y-1">
                {failedRequests.values.slice(0, 10).map((url) => (
                  <li key={url} className="truncate font-mono text-xs text-muted-foreground">{url}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {/* Limitations */}
      <Card>
        <CardContent className="pt-4">
          <p className="text-xs text-muted-foreground">
            These are measurements from a single cold lab run from one network location.
            They represent what this particular scan observed and will differ across runs,
            locations, and network conditions. They are not representative of real-user experience.
            No performance score is produced because a single measurement cannot meaningfully rate a website.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({ label, value, explanation }: { label: string; value: string; explanation: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="font-mono text-lg font-semibold tabular-nums">{value}</p>
      <p className="text-xs font-medium">{label}</p>
      <p className="mt-0.5 text-[10px] text-muted-foreground">{explanation}</p>
    </div>
  );
}

function findValue(findings: Finding[], id: string): number | null {
  const f = findings.find((item) => item.id === id);
  return typeof f?.value === 'number' ? f.value : null;
}
