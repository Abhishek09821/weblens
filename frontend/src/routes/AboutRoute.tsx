import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useCapabilities } from '@/features/scan/useHealth';

/**
 * Methodology and limitations.
 *
 * Published in the product, not just in the repository: a tool that makes claims about other
 * people's websites owes its users a plain account of how it reaches them and where it stops.
 */
export function AboutRoute() {
  const capabilities = useCapabilities();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Methodology and limitations</h1>
        <p className="text-sm text-muted-foreground">
          How WebLens reaches its conclusions, and what it cannot tell you.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>How detection works</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            A scan collects evidence once — HTTP response headers, the served document, DNS and
            robots observations, and (when a browser is available) the rendered DOM, computed styles,
            performance entries and network ledger. Deterministic analyzers then read that evidence.
          </p>
          <p>
            <strong className="text-foreground">No AI model performs detection.</strong> The optional
            explanation layer only rephrases findings that already exist, and any statement it
            produces that cannot be traced to a finding is discarded.
          </p>
          <p>
            Each finding carries the evidence supporting it. A claim without evidence cannot be
            constructed by the backend, so it cannot reach this screen or a downloaded report.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Finding statuses</CardTitle>
          <CardDescription>The five outcomes, and what each does and does not mean.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="space-y-3 text-sm">
            <StatusEntry term="Verified">
              Directly observed in the collected evidence.
            </StatusEntry>
            <StatusEntry term="Inferred">
              Derived from indirect signals. The signals are shown so you can judge them yourself.
            </StatusEntry>
            <StatusEntry term="Not detected">
              Evidence was collected and the signal was absent. This is <em>not</em> the same as “not
              used”: server-rendered, self-hosted, or heavily bundled technologies are frequently
              invisible from outside.
            </StatusEntry>
            <StatusEntry term="Not determinable">
              The property cannot be observed from outside the site at all.
            </StatusEntry>
            <StatusEntry term="Unable to verify">
              The evidence needed for the check was not collected in this scan.
            </StatusEntry>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Observable Security Posture</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            Security is the only section with a score, because presence and quality of observable
            defensive configuration is genuinely useful to communicate. Every rule, weight, and band
            is published, and rules that could not be evaluated are excluded from both sides of the
            ratio and listed.
          </p>
          <p>
            It is not a vulnerability assessment, a penetration test, or a compliance rating. It
            cannot establish that a site is secure or insecure. No other section is scored, because
            any score for design, technology, or architecture would be an invented weighting
            presented as a measurement.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What WebLens does not do</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1.5 pl-4 text-sm text-muted-foreground">
            <li>
              No offensive testing: no exploitation, credential attacks, authentication bypass,
              brute force, fuzzing, or destructive requests.
            </li>
            <li>No crawling. One URL per scan, so findings describe that page only.</li>
            <li>
              No authenticated, paywalled, or geo-restricted content, and no bypassing of bot
              protection or consent walls.
            </li>
            <li>
              One cold run from one network location with one viewport, so performance numbers are lab
              observations rather than field data, and no performance score is produced.
            </li>
            <li>
              Automated accessibility rules cover a subset of WCAG. A clean result does not mean a
              site is accessible; conformance needs manual testing with assistive technologies and
              expert review.
            </li>
            <li>
              Scans are stored in this browser only. Deleting one is permanent — there is no server
              copy.
            </li>
          </ul>
        </CardContent>
      </Card>

      {capabilities.data && (
        <Card>
          <CardHeader>
            <CardTitle>This build</CardTitle>
            <CardDescription>
              Engine {capabilities.data.engine_version} · result schema{' '}
              {capabilities.data.schema_version} · collection mode{' '}
              {capabilities.data.collection_mode}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <caption className="sr-only">Analyzers declared in this build</caption>
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-1.5 font-medium">Analyzer</th>
                  <th scope="col" className="py-1.5 font-medium">State</th>
                  <th scope="col" className="py-1.5 font-medium">Purpose</th>
                </tr>
              </thead>
              <tbody>
                {capabilities.data.analyzers.map((entry) => (
                  <tr key={entry.id} className="border-b border-border/50 last:border-0 align-top">
                    <td className="py-1.5 pr-3 font-mono text-xs">{entry.id}</td>
                    <td className="py-1.5 pr-3 text-xs">
                      {entry.implemented ? 'implemented' : `phase ${entry.planned_phase}`}
                    </td>
                    <td className="py-1.5 text-xs text-muted-foreground">{entry.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatusEntry({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="font-medium">{term}</dt>
      <dd className="text-muted-foreground">{children}</dd>
    </div>
  );
}
