import { seoPayloadSchema } from '@/types/analysis';

import { heading, keyValueTable, section as join, table } from '../kit';
import { standardDocument, type RenderContext } from '../shared';

/**
 * SEO report.
 *
 * Adds the metadata summary and structured-data inventory on top of the standard findings tables.
 * The payload is parsed rather than cast: a stored result from a different build must degrade to
 * "findings only" instead of throwing while a user is trying to download a report.
 */
export function renderSeo(ctx: RenderContext): string {
  const parsed = seoPayloadSchema.safeParse(ctx.section.data);
  if (!parsed.success) {
    return standardDocument(ctx, 'SEO');
  }
  const payload = parsed.data;
  const metadata = payload.metadata;

  const metadataBlock = metadata
    ? join(
        heading(2, 'Document metadata'),
        keyValueTable([
          ['Title', metadata.title],
          ['Title length', metadata.title_length],
          ['Meta description', metadata.description],
          ['Description length', metadata.description_length],
          ['Canonical URL', metadata.canonical],
          ['Robots meta', metadata.robots_meta],
          ['Viewport meta', metadata.viewport_meta],
          ['Charset', metadata.charset],
          ['Document language', metadata.lang],
          ['h1 headings', metadata.h1_texts.length > 0 ? metadata.h1_texts.join(' | ') : null],
        ]),
      )
    : '';

  const socialBlock =
    metadata && (metadata.open_graph.length > 0 || metadata.twitter.length > 0)
      ? join(
          heading(2, 'Social metadata'),
          table(
            ['Property', 'Value'],
            [
              ...metadata.open_graph.map((entry) => [entry.key, entry.value]),
              ...metadata.twitter.map((entry) => [entry.key, entry.value]),
            ],
          ),
        )
      : '';

  const internationalBlock =
    metadata && metadata.hreflang.length > 0
      ? join(
          heading(2, 'Language alternates'),
          table(
            ['hreflang', 'href'],
            metadata.hreflang.map((entry) => [entry.hreflang, entry.href]),
          ),
        )
      : '';

  const structuredBlock =
    payload.structured_data.length > 0
      ? join(
          heading(2, 'Structured data'),
          table(
            ['Format', 'Types', 'Valid', 'Parse error', 'Length'],
            payload.structured_data.map((block) => [
              block.format,
              block.types.join(', '),
              block.valid ? 'yes' : 'no',
              block.parse_error,
              block.raw_length,
            ]),
          ),
        )
      : '';

  return standardDocument(
    ctx,
    'SEO',
    metadataBlock,
    socialBlock,
    internationalBlock,
    structuredBlock,
  );
}
