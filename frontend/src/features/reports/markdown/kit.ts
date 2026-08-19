/**
 * Markdown building blocks.
 *
 * Everything a scanned page sends us is untrusted text that ends up inside a Markdown table. The
 * escaping here is the last line of defence: a page whose title contains a pipe or a newline must
 * not be able to break out of a cell or inject a fake heading into a report.
 */

export function heading(level: number, text: string): string {
  return `${'#'.repeat(Math.min(Math.max(level, 1), 6))} ${text}`;
}

export function paragraph(text: string): string {
  return text;
}

export function bullets(items: string[]): string {
  return items.map((item) => `- ${item}`).join('\n');
}

export function numbered(items: string[]): string {
  return items.map((item, index) => `${index + 1}. ${item}`).join('\n');
}

/** Escape text for use inside a table cell. */
export function cell(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  return String(value)
    .replace(/\\/g, '\\\\')
    .replace(/\|/g, '\\|')
    .replace(/\r?\n|\r/g, ' ')
    .replace(/`/g, '\\`')
    .trim();
}

export function table(headers: string[], rows: unknown[][]): string {
  if (rows.length === 0) return '_No rows._';
  const head = `| ${headers.join(' | ')} |`;
  const divider = `| ${headers.map(() => '---').join(' | ')} |`;
  const body = rows.map((row) => `| ${row.map(cell).join(' | ')} |`).join('\n');
  return [head, divider, body].join('\n');
}

export function keyValueTable(pairs: [string, unknown][]): string {
  return table(['Field', 'Value'], pairs.map(([key, value]) => [key, value]));
}

/**
 * Fenced code block with a fence long enough to contain the content.
 *
 * A page can legitimately contain triple backticks; a fixed fence would let it terminate the block
 * early and inject Markdown into the report.
 */
export function codeBlock(content: string, language = ''): string {
  const longestRun = [...content.matchAll(/`+/g)].reduce(
    (max, match) => Math.max(max, match[0].length),
    0,
  );
  const fence = '`'.repeat(Math.max(3, longestRun + 1));
  return `${fence}${language}\n${content}\n${fence}`;
}

export function inlineCode(value: string): string {
  return `\`${value.replace(/`/g, '\u02cb')}\``;
}

export function blockquote(text: string): string {
  return text
    .split('\n')
    .map((line) => `> ${line}`)
    .join('\n');
}

export function section(...parts: (string | null | undefined | false)[]): string {
  return parts.filter((part): part is string => Boolean(part)).join('\n\n');
}

export function detailsBlock(summary: string, body: string): string {
  return `<details>\n<summary>${summary}</summary>\n\n${body}\n\n</details>`;
}
