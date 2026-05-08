import { useQuery } from '@tanstack/react-query'

import type { ResearchJob } from '../types/api'

/*
 * TODO: replace placeholder with real `GET /api/research` call.
 * The backend list endpoint is not yet implemented; this hook returns an
 * empty array so the sidebar empty-state UI is already in place.
 */
export function useResearchHistory() {
  return useQuery<ResearchJob[]>({
    queryKey: ['research', 'list'],
    queryFn: async () => [],
    staleTime: Infinity,
  })
}
