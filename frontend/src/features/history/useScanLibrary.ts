/**
 * The local scan library.
 *
 * Reads come from IndexedDB through TanStack Query, so the cache is a view over persisted data
 * rather than a second source of truth. Deep links keep working after a browser restart with the
 * backend stopped, which is the acceptance test for the persistence layer.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import { getRepository } from '@/lib/db/repository';
import type { ScanRecord } from '@/lib/db/types';
import type { AnalysisResult } from '@/types/analysis';

const SCANS_KEY = ['scans'] as const;

export function useScanLibrary() {
  return useQuery<ScanRecord[]>({
    queryKey: SCANS_KEY,
    queryFn: () => getRepository().list(),
    staleTime: 0,
  });
}

export function useStoredResult(scanId: string | undefined) {
  return useQuery<AnalysisResult | null>({
    queryKey: ['scan', scanId, 'result'],
    queryFn: async () => (scanId ? ((await getRepository().getResult(scanId)) ?? null) : null),
    enabled: Boolean(scanId),
    staleTime: Infinity,
  });
}

export function useStoredScreenshots(scanId: string | undefined) {
  return useQuery({
    queryKey: ['scan', scanId, 'screenshots'],
    queryFn: async () => (scanId ? getRepository().getScreenshots(scanId) : []),
    enabled: Boolean(scanId),
    staleTime: Infinity,
  });
}

export function useQuarantinedScans() {
  return useQuery({
    queryKey: ['scans', 'quarantined'],
    queryFn: () => getRepository().quarantined(),
    staleTime: 60_000,
  });
}

/**
 * Delete a scan and everything belonging to it.
 *
 * Removal is permanent by design: there is no server copy to restore from, which the confirmation
 * dialog states plainly. The server buffer is also released, harmlessly, in case it still exists.
 */
export function useDeleteScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (scanId: string) => {
      await getRepository().remove(scanId);
      await api.deleteScan(scanId);
    },
    onSuccess: (_data, scanId) => {
      void queryClient.invalidateQueries({ queryKey: SCANS_KEY });
      queryClient.removeQueries({ queryKey: ['scan', scanId] });
    },
  });
}

export function useClearLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => getRepository().clear(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: SCANS_KEY });
      queryClient.removeQueries({ queryKey: ['scan'] });
    },
  });
}
