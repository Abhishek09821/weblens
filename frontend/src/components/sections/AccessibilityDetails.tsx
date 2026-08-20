/**
 * Accessibility — human-readable issue presentation.
 *
 * Shows issues grouped by concern (images, forms, headings, landmarks)
 * with explanations of why each matters.
 * Raw axe-core details available in expandable evidence.
 */
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { AnalysisResult, Finding } from '@/types/analysis';

export function AccessibilityDetails({ result }: { result: AnalysisResult }) {
  const section = result.sections.accessibility;
  const findings = section.findings;

  // Group findings by concern
  const docLang = find(findings, 'accessibility.structure:document-lang');
  const docTitle = find(findings, 'accessibility.structure:document-title');
  const headings = find(findings, 'accessibility.structure:heading-hierarchy');
  const imagesAlt = find(findings, 'accessibility.structure:images-missing-alt');
  const imagesCoverage = find(findings, 'accessibility.structure:images-alt-coverage');
  const formLabels = find(findings, 'accessibility.structure:form-labels');
  const landmarks = find(findings, 'accessibility.structure:landmarks');
  const tabindex = find(findings, 'accessibility.structure:positive-tabindex');
  const violationCount = find(findings, 'accessibility.axe:violation-count');
  const violationsByImpact = find(findings, 'accessibility.axe:violations-by-impact');

  // axe-core execution error
  const axeError = find(findings, 'accessibility.axe:execution-error');

  return (
    <div className="space-y-5">
      {/* Automated Testing Summary */}
      {violationCount && typeof violationCount.value === 'number' && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Automated Testing Results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-2xl font-semibold">
                {violationCount.value}
              </span>
              <span className="text-sm text-muted-foreground">
                rule violation{violationCount.value !== 1 ? 's' : ''} detected
              </span>
            </div>
            {violationsByImpact?.values && violationsByImpact.values.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {violationsByImpact.values.map((entry) => (
                  <Badge key={entry} variant={entry.startsWith('critical') || entry.startsWith('serious') ? 'attention' : 'muted'}>
                    {entry}
                  </Badge>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Automated rules detect a subset of WCAG issues. A clean result does not mean a site
              is accessible — conformance requires manual testing with assistive technologies.
            </p>
          </CardContent>
        </Card>
      )}

      {axeError && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-status-attention">
              Automated accessibility engine was unavailable for this scan. Structural checks below
              still ran, but the comprehensive rule set could not be evaluated.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Document Structure */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Document Structure</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <IssueRow
            finding={docLang}
            good="Document declares a language"
            bad="Document is missing a language declaration"
            why="Screen readers use this to select the correct pronunciation."
          />
          <IssueRow
            finding={docTitle}
            good="Document has a title"
            bad="Document is missing a title"
            why="The title identifies the page to screen readers and in browser tabs."
          />
          <IssueRow
            finding={headings}
            good={headings?.value === 'correct' ? 'Heading hierarchy is correct' : undefined}
            bad={headings?.values?.length ? `Heading hierarchy issue: ${headings.values[0]}` : 'Heading hierarchy has issues'}
            why="Proper heading levels let screen reader users navigate by document structure."
            isIssue={headings?.value !== 'correct' && headings?.values !== undefined && headings.values.length > 0}
          />
          <IssueRow
            finding={landmarks}
            good={landmarks?.detected ? `${landmarks.value} ARIA landmarks present` : undefined}
            bad="No ARIA landmarks detected"
            why="Landmarks help assistive technology users jump to major page regions."
          />
        </CardContent>
      </Card>

      {/* Images */}
      {(imagesAlt || imagesCoverage) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Images</CardTitle>
          </CardHeader>
          <CardContent>
            {imagesAlt && typeof imagesAlt.value === 'number' && imagesAlt.value > 0 ? (
              <div className="space-y-2">
                <p className="text-sm">
                  <strong className="text-status-attention">{imagesAlt.value}</strong> image{imagesAlt.value > 1 ? 's do' : ' does'} not
                  have an <code className="rounded bg-muted px-1 py-0.5 text-xs">alt</code> attribute.
                </p>
                <p className="text-xs text-muted-foreground">
                  Images without alternative text are invisible to screen reader users and fail
                  to convey information when images cannot be displayed.
                </p>
              </div>
            ) : imagesCoverage ? (
              <p className="text-sm text-muted-foreground">All images have alt attributes.</p>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Forms */}
      {formLabels && typeof formLabels.value === 'number' && formLabels.value > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Forms</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm">
              <strong className="text-status-attention">{formLabels.value}</strong> form
              input{formLabels.value > 1 ? 's' : ''} without associated labels.
            </p>
            <p className="text-xs text-muted-foreground">
              Inputs without labels are difficult to identify for screen reader users and do not
              receive a visible label for sighted users on some platforms.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Tabindex */}
      {tabindex && typeof tabindex.value === 'number' && tabindex.value > 0 && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-status-attention">
              {tabindex.value} element{tabindex.value > 1 ? 's have' : ' has'} a positive tabindex value,
              which overrides the natural tab order and often confuses keyboard navigation.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function IssueRow({
  finding,
  good,
  bad,
  why,
  isIssue,
}: {
  finding: Finding | undefined;
  good?: string;
  bad: string;
  why: string;
  isIssue?: boolean;
}) {
  if (!finding) return null;
  const detected = finding.detected ?? false;
  const showAsIssue = isIssue !== undefined ? isIssue : !detected;

  return (
    <div className="flex items-start gap-3 rounded-md border border-border p-2.5">
      <div className={`mt-0.5 size-2 shrink-0 rounded-full ${showAsIssue ? 'bg-status-attention' : 'bg-status-verified'}`} />
      <div className="min-w-0">
        <p className="text-sm">
          {showAsIssue ? bad : (good ?? finding.name)}
        </p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">{why}</p>
      </div>
    </div>
  );
}

function find(findings: Finding[], id: string): Finding | undefined {
  return findings.find((f) => f.id === id);
}
