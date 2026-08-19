/**
 * Scan lifecycle driver.
 *
 * Progress comes from real backend stage events over SSE, with polling as a fallback. There is no
 * timer-driven animation standing in for progress: when nothing has changed, the UI shows the
 * current stage and an elapsed clock, which is the honest thing to show.
 *
 * The final step matters as much as the scan: the result is fetched, validated, written to
 * IndexedDB, and only then is the server-side copy released. The browser is the system of record.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { api, type ScanRequestOptions } from '@/lib/api/client';
import { describeError } from '@/lib/api/errors';
import { getRepository } from '@/lib/db/repository';
import type { ScreenshotItem } from '@/lib/db/types';
import { validateUrlInput } from '@/lib/url-validation';
import { scanJobStateSchema, type AnalysisResult, type ScanJobState } from '@/types/analysis';

import type { ScanPhase } from './types';

const POLL_INTERVAL_MS = 700;

export interface ScanRunner {
  phase: ScanPhase;
  start: (url: string, options?: ScanRequestOptions) => Promise<void>;
  reset: () => void;
  elapsedMs: number;
}

export function useScanRunner(onReady?: (scanId: string) => void): ScanRunner {
  const [phase, setPhase] = useState<ScanPhase>({ kind: 'idle' });
  const [elapsedMs, setElapsedMs] = useState(0);

  const sourceRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);
  const settledRef = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      teardown(sourceRef, pollRef);
    };
  }, []);

  // Elapsed clock: shown instead of a fabricated percentage while a stage is in flight.
  useEffect(() => {
    if (phase.kind !== 'running' && phase.kind !== 'submitting' && phase.kind !== 'persisting') {
      return;
    }
    const timer = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAtRef.current);
    }, 200);
    return () => window.clearInterval(timer);
  }, [phase.kind]);

  const finish = useCallback(
    async (scanId: string) => {
      if (settledRef.current) return;
      settledRef.current = true;
      teardown(sourceRef, pollRef);

      setPhase({ kind: 'persisting', scanId });
      try {
        const result = await api.result(scanId);
        const screenshots = await decodeScreenshots(result);
        const outcome = await getRepository().persist(result, screenshots);
        await api.deleteScan(scanId);

        if (!mountedRef.current) return;
        setPhase({
          kind: 'ready',
          scanId,
          hasErrors: result.errors.length > 0 || result.scan.status === 'completed_with_errors',
          ...(outcome.warning ? { warning: outcome.warning } : {}),
        });
        onReady?.(scanId);
      } catch (error) {
        if (!mountedRef.current) return;
        const described = describeError(error);
        setPhase({
          kind: 'failed',
          problem: null,
          title: described.title,
          detail: `${described.detail} The scan itself may have completed; it could not be stored locally.`,
        });
      }
    },
    [onReady],
  );

  const observe = useCallback(
    (scanId: string) => {
      const applyJob = (job: ScanJobState) => {
        if (!mountedRef.current) return;
        if (job.status === 'failed' || job.status === 'cancelled') {
          settledRef.current = true;
          teardown(sourceRef, pollRef);
          setPhase({
            kind: 'failed',
            problem: job.problem ?? null,
            title: job.problem?.title ?? 'The scan did not complete',
            detail: job.problem?.detail ?? 'The backend reported no further detail.',
          });
          return;
        }
        if (job.status === 'completed' || job.status === 'completed_with_errors') {
          void finish(scanId);
          return;
        }
        setPhase({ kind: 'running', scanId, job });
      };

      const refresh = async () => {
        try {
          applyJob(await api.jobState(scanId));
        } catch (error) {
          if (settledRef.current) return;
          const described = describeError(error);
          setPhase({
            kind: 'failed',
            problem: null,
            title: described.title,
            detail: described.detail,
          });
          teardown(sourceRef, pollRef);
        }
      };

      const startPolling = () => {
        if (pollRef.current !== null || settledRef.current) return;
        pollRef.current = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
      };

      if (typeof EventSource === 'undefined') {
        startPolling();
        void refresh();
        return;
      }

      const source = new EventSource(api.eventsUrl(scanId));
      sourceRef.current = source;

      source.addEventListener('snapshot', (event) => {
        const parsed = scanJobStateSchema.safeParse(safeJson((event as MessageEvent<string>).data));
        if (parsed.success) applyJob(parsed.data);
      });
      // Stage and progress frames are small; re-reading the job state keeps one source of truth
      // for what the UI displays.
      source.addEventListener('stage', () => void refresh());
      source.addEventListener('progress', () => void refresh());
      source.addEventListener('done', () => void finish(scanId));
      source.addEventListener('error', () => void refresh());
      source.onerror = () => {
        // The stream also "errors" on normal close after `done`; polling covers both cases.
        if (settledRef.current) return;
        source.close();
        sourceRef.current = null;
        startPolling();
      };
    },
    [finish],
  );

  const start = useCallback(
    async (url: string, options?: ScanRequestOptions) => {
      const validation = validateUrlInput(url);
      if (!validation.valid) {
        setPhase({ kind: 'invalid', message: validation.message ?? 'That URL cannot be analyzed.' });
        return;
      }

      teardown(sourceRef, pollRef);
      settledRef.current = false;
      startedAtRef.current = Date.now();
      setElapsedMs(0);
      setPhase({ kind: 'submitting', url: validation.normalized ?? url });

      try {
        const accepted = await api.createScan(validation.normalized ?? url, options);
        if (!mountedRef.current) return;
        setPhase({ kind: 'running', scanId: accepted.scan_id, job: null });
        observe(accepted.scan_id);
      } catch (error) {
        if (!mountedRef.current) return;
        const described = describeError(error);
        setPhase({
          kind: 'failed',
          problem: null,
          title: described.title,
          detail: described.detail,
        });
      }
    },
    [observe],
  );

  const reset = useCallback(() => {
    teardown(sourceRef, pollRef);
    settledRef.current = false;
    setElapsedMs(0);
    setPhase({ kind: 'idle' });
  }, []);

  return { phase, start, reset, elapsedMs };
}

function teardown(
  sourceRef: React.RefObject<EventSource | null>,
  pollRef: React.RefObject<number | null>,
): void {
  sourceRef.current?.close();
  sourceRef.current = null;
  if (pollRef.current !== null) {
    window.clearInterval(pollRef.current);
    pollRef.current = null;
  }
}

function safeJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/** Move screenshot bytes out of the result and into Blobs for the screenshots store. */
async function decodeScreenshots(result: AnalysisResult): Promise<ScreenshotItem[]> {
  const items: ScreenshotItem[] = [];
  for (const shot of result.screenshots) {
    try {
      const binary = atob(shot.data_base64);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      items.push({
        label: shot.label,
        width: shot.width,
        height: shot.height,
        blob: new Blob([bytes], { type: shot.mime_type }),
      });
    } catch {
      // A screenshot that cannot be decoded is dropped rather than stored corrupt. The record's
      // `has_screenshot` flag then reflects reality.
    }
  }
  return items;
}
