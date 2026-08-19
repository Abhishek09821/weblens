import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api/client';
import type { Capabilities, Health } from '@/types/analysis';

/** Backend liveness and browser readiness, used for pre-flight warnings. */
export function useHealth() {
  return useQuery<Health>({
    queryKey: ['health'],
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 60_000,
    retry: false,
  });
}

/**
 * What this build can analyze.
 *
 * The dashboard renders section availability from this rather than assuming, so an analyzer that
 * has not shipped yet is shown as such instead of appearing to have found nothing.
 */
export function useCapabilities() {
  return useQuery<Capabilities>({
    queryKey: ['capabilities'],
    queryFn: ({ signal }) => api.capabilities(signal),
    staleTime: 5 * 60_000,
  });
}
