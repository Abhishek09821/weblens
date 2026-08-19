/**
 * Zip assembly and downloads.
 *
 * Entry names come from the fixed renderer registry, never from target-controlled input, so a
 * hostile page cannot influence a path inside the archive. Object URLs are revoked on every path,
 * including failures.
 */
import { zip } from 'fflate';

import type { ScreenshotItem } from '@/lib/db/types';

import type { ReportBundle, ReportFile } from './generate';

export async function bundleToZip(
  bundle: ReportBundle,
  screenshots: ScreenshotItem[] = [],
): Promise<Blob> {
  const encoder = new TextEncoder();
  const entries: Record<string, Uint8Array> = {};

  for (const item of bundle.files) {
    entries[item.path] = encoder.encode(item.contents);
  }

  for (const [index, shot] of screenshots.entries()) {
    const safeLabel = shot.label.replace(/[^a-z0-9_-]+/gi, '-').toLowerCase() || `shot-${index}`;
    entries[`screenshots/${safeLabel}.png`] = new Uint8Array(await shot.blob.arrayBuffer());
  }

  return new Promise<Blob>((resolve, reject) => {
    // Level 6 keeps a large result's zip fast enough to stay off the main thread's critical path.
    zip(entries, { level: 6 }, (error, data) => {
      if (error) {
        reject(new Error(`Could not build the report archive: ${error.message}`));
        return;
      }
      resolve(new Blob([data as BlobPart], { type: 'application/zip' }));
    });
  });
}

export function downloadBlob(blob: Blob, filename: string): void {
  if (typeof document === 'undefined') return;
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = 'noopener';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    // Revoke on a later tick so the navigation has started, but always revoke.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function downloadText(file: ReportFile, filename = file.path): void {
  downloadBlob(new Blob([file.contents], { type: 'text/markdown;charset=utf-8' }), filename);
}

export function downloadJson(contents: string, filename: string): void {
  downloadBlob(new Blob([contents], { type: 'application/json;charset=utf-8' }), filename);
}
