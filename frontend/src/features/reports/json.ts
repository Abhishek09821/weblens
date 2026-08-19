/**
 * `analysis.json` serialization.
 *
 * Keys are sorted so two exports of the same result are byte-identical. That is what makes report
 * snapshot tests meaningful and lets users diff two scans of the same site without noise from key
 * ordering.
 */
import type { AnalysisResult } from '@/types/analysis';

export function stableStringify(value: unknown, indent = 2): string {
  return `${JSON.stringify(value, sortedReplacer(), indent)}\n`;
}

export function renderAnalysisJson(result: AnalysisResult): string {
  return stableStringify(result);
}

function sortedReplacer() {
  return function replacer(this: unknown, _key: string, value: unknown): unknown {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) return value;
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) =>
      a.localeCompare(b),
    );
    return Object.fromEntries(entries);
  };
}
