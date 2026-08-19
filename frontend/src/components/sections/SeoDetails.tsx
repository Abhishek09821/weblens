import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { seoPayloadSchema, type Section } from '@/types/analysis';

/**
 * SEO payload detail.
 *
 * Parsed rather than cast, so a stored result from a different build degrades to the findings table
 * instead of crashing the dashboard.
 */
export function SeoDetails({ section }: { section: Section }) {
  const parsed = seoPayloadSchema.safeParse(section.data);
  if (!parsed.success) return null;

  const { metadata, structured_data: structuredData } = parsed.data;
  if (!metadata && structuredData.length === 0) return null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {metadata && (
        <Card>
          <CardHeader>
            <CardTitle>Document metadata</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <FieldRow label="Title" value={metadata.title} meta={lengthLabel(metadata.title_length)} />
            <FieldRow
              label="Description"
              value={metadata.description}
              meta={lengthLabel(metadata.description_length)}
            />
            <FieldRow label="Canonical" value={metadata.canonical} mono />
            <FieldRow label="Robots" value={metadata.robots_meta} mono />
            <FieldRow label="Viewport" value={metadata.viewport_meta} mono />
            <FieldRow label="Language" value={metadata.lang} mono />
            <FieldRow label="Charset" value={metadata.charset} mono />
            {metadata.h1_texts.length > 0 && (
              <FieldRow label="h1" value={metadata.h1_texts.join(' · ')} />
            )}
            {(metadata.open_graph.length > 0 || metadata.twitter.length > 0) && (
              <div>
                <p className="mb-1 text-xs text-muted-foreground">Social tags</p>
                <div className="flex flex-wrap gap-1">
                  {[...metadata.open_graph, ...metadata.twitter].map((entry) => (
                    <Badge key={entry.key} variant="outline" className="font-mono">
                      {entry.key}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {structuredData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Structured data</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {structuredData.map((block, index) => (
              <div
                key={`${block.format}-${index}`}
                className="flex flex-wrap items-center gap-2 rounded-md border border-border px-2.5 py-2"
              >
                <Badge variant="muted" className="font-mono">
                  {block.format}
                </Badge>
                <Badge variant={block.valid ? 'verified' : 'attention'}>
                  {block.valid ? 'parses' : 'invalid syntax'}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {block.types.length > 0 ? block.types.join(', ') : 'no @type declared'}
                </span>
                {block.parse_error && (
                  <span className="w-full font-mono text-[11px] text-muted-foreground">
                    {block.parse_error}
                  </span>
                )}
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              Blocks are checked for syntax and type inventory only, not eligibility for any search
              feature.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function FieldRow({
  label,
  value,
  meta,
  mono = false,
}: {
  label: string;
  value: string | null | undefined;
  meta?: string;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[7rem_1fr] items-start gap-2 text-sm">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={mono ? 'break-words font-mono text-[13px]' : 'break-words'}>
        {value ?? <span className="text-muted-foreground">not present</span>}
        {meta && <span className="ml-2 text-xs text-muted-foreground">{meta}</span>}
      </span>
    </div>
  );
}

function lengthLabel(length: number | null | undefined): string | undefined {
  return typeof length === 'number' ? `${length} chars` : undefined;
}
