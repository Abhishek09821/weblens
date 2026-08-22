/**
 * Design analysis — transforms CSS measurements into understandable design information.
 *
 * Shows color swatches, typography systems, layout patterns, and media usage.
 * Technical evidence is available through expandable sections.
 */
import { FindingStatusBadge } from '@/components/sections/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatFindingValue } from '@/lib/format/status';
import { buildDesignPresentation } from '@/lib/presentation/design';
import { designPayloadSchema, type AnalysisResult, type Finding } from '@/types/analysis';

export function DesignDetails({ result }: { result: AnalysisResult }) {
  const design = buildDesignPresentation(result);
  const section = result.sections.design;
  const payload = designPayloadSchema.safeParse(section.data);
  const coverage = payload.success ? payload.data.coverage : null;
  const structureFindings = section.findings.filter((finding) =>
    ['document', 'structure'].includes(finding.category),
  );
  const componentFindings = section.findings.filter((finding) => finding.category === 'forms');

  return (
    <div className="space-y-5">
      {/* Summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Design Reconstruction</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">{design.summary}</p>
          {coverage && (
            <p className="text-xs text-muted-foreground">
              Sample coverage: {coverage.elements_sampled} element
              {coverage.elements_sampled === 1 ? '' : 's'} inspected
              {coverage.elements_total != null ? ` of ${coverage.elements_total}` : ''}
              {coverage.cap_hit ? ' (collection cap reached)' : ''}.
            </p>
          )}
        </CardContent>
      </Card>

      <ObservationCard title="Page Structure" findings={structureFindings} />

      {/* Color System */}
      {design.colors.available && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Color System</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {design.colors.backgrounds.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Background Colors
                </p>
                <div className="flex flex-wrap gap-2">
                  {design.colors.backgrounds.map((color, i) => (
                    <ColorSwatch key={i} color={color.value} hex={color.hex} />
                  ))}
                </div>
              </div>
            )}
            {design.colors.texts.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Text Colors
                </p>
                <div className="flex flex-wrap gap-2">
                  {design.colors.texts.map((color, i) => (
                    <ColorSwatch key={i} color={color.value} hex={color.hex} />
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Typography */}
      {design.typography.available && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Typography</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {design.typography.loadedFonts.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Fonts Loaded
                </p>
                <div className="flex flex-wrap gap-2">
                  {design.typography.loadedFonts.map((font) => (
                    <span key={font} className="rounded-md border border-border px-2.5 py-1 text-sm">
                      {font}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {design.typography.weights.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Font Weights
                </p>
                <div className="flex flex-wrap gap-2">
                  {design.typography.weights.map((w) => (
                    <span key={w} className="rounded border border-border px-2 py-0.5 font-mono text-xs">
                      {w}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {design.typography.sizes.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Font Sizes (type scale)
                </p>
                <div className="flex flex-wrap gap-2">
                  {design.typography.sizes.map((s) => (
                    <span key={s} className="rounded border border-border px-2 py-0.5 font-mono text-xs">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Layout */}
      {design.layout.available && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Layout, Spacing & Responsive Behavior</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {design.layout.displayTypes.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Layout Methods
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {design.layout.displayTypes.map((d) => (
                    <span key={d} className="rounded border border-border px-2 py-0.5 font-mono text-xs">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {design.layout.borderRadii.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Border Radius Values
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {design.layout.borderRadii.map((r) => (
                    <span key={r} className="rounded border border-border px-2 py-0.5 font-mono text-xs">
                      {r}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {design.layout.gaps.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Spacing / Gap Values
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {design.layout.gaps.map((gap) => (
                    <span key={gap} className="rounded border border-border px-2 py-0.5 font-mono text-xs">
                      {gap}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {design.layout.shadows.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Component Shadow Patterns
                </p>
                <ul className="space-y-1 font-mono text-xs text-muted-foreground">
                  {design.layout.shadows.map((shadow) => <li key={shadow}>{shadow}</li>)}
                </ul>
              </div>
            )}
            {design.layout.breakpoints.length > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Responsive Breakpoints
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {design.layout.breakpoints.map((bp) => (
                    <span key={bp} className="rounded border border-border px-2 py-0.5 font-mono text-xs">
                      {bp}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {design.layout.hasOverflow && (
              <p className="text-xs text-status-attention">
                Horizontal overflow detected at viewport widths: {design.layout.overflowWidths.join(', ')}px
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <ObservationCard title="Components & Patterns" findings={componentFindings} />

      {/* Motion */}
      {design.motion.available && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Motion & Animation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {design.motion.transitions.length > 0 && (
              <div>
                <p className="text-xs text-muted-foreground">
                  {design.motion.transitions.length} CSS transition pattern{design.motion.transitions.length > 1 ? 's' : ''} observed
                </p>
              </div>
            )}
            {design.motion.keyframeCount !== null && design.motion.keyframeCount > 0 && (
              <p className="text-xs text-muted-foreground">
                {design.motion.keyframeCount} @keyframes animation definition{design.motion.keyframeCount > 1 ? 's' : ''}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Media */}
      {design.media.available && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Media & Images</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {design.media.imageCount !== null && (
                <MediaStat label="Images" value={design.media.imageCount} detail={
                  design.media.lazyLoaded ? `${design.media.lazyLoaded} lazy-loaded` : undefined
                } />
              )}
              {design.media.svgCount !== null && design.media.svgCount > 0 && (
                <MediaStat label="SVGs" value={design.media.svgCount} />
              )}
              {design.media.videoCount !== null && design.media.videoCount > 0 && (
                <MediaStat label="Videos" value={design.media.videoCount} />
              )}
              {design.media.pictureCount !== null && design.media.pictureCount > 0 && (
                <MediaStat label="<picture>" value={design.media.pictureCount} detail="Responsive images" />
              )}
            </div>
            {design.media.formats.length > 0 && (
              <div className="mt-3">
                <p className="mb-1 text-xs text-muted-foreground">Image formats:</p>
                <p className="text-xs font-mono">{design.media.formats.join(', ')}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ObservationCard({ title, findings }: { title: string; findings: Finding[] }) {
  if (findings.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {findings.map((finding) => (
            <li key={finding.id} className="py-2 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm">{finding.name}</span>
                <div className="flex items-center gap-2">
                  {(finding.value !== null || finding.values.length > 0) && (
                    <span className="font-mono text-xs">{formatFindingValue(finding)}</span>
                  )}
                  <FindingStatusBadge status={finding.status} />
                </div>
              </div>
              {finding.reason && <p className="mt-1 text-xs text-muted-foreground">{finding.reason}</p>}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function ColorSwatch({ color, hex }: { color: string; hex: string | null }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border px-2 py-1">
      <div
        className="size-5 rounded border border-border/50"
        style={{ backgroundColor: color }}
        title={color}
      />
      <span className="font-mono text-[11px]">{hex ?? color}</span>
    </div>
  );
}

function MediaStat({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <div>
      <p className="font-mono text-lg font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
      {detail && <p className="text-[10px] text-muted-foreground">{detail}</p>}
    </div>
  );
}
