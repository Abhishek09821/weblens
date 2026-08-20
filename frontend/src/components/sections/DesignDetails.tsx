/**
 * Design analysis — transforms CSS measurements into understandable design information.
 *
 * Shows color swatches, typography systems, layout patterns, and media usage.
 * Technical evidence is available through expandable sections.
 */
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { buildDesignPresentation } from '@/lib/presentation/design';
import type { AnalysisResult } from '@/types/analysis';

export function DesignDetails({ result }: { result: AnalysisResult }) {
  const design = buildDesignPresentation(result);

  return (
    <div className="space-y-5">
      {/* Summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Overall Design</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{design.summary}</p>
        </CardContent>
      </Card>

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
            <CardTitle className="text-base">Layout & Spacing</CardTitle>
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
