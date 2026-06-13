import { useInfiniteQuery } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { listResearchApiResearchGet } from '../types/api'
import type { JobListResponse } from '../types/api'

const PAGE_SIZE = 20

/*
 * Paginated history of the user's research jobs (GET /api/research).
 *
 * Keyed `['research', 'list']` — the same key `useStartResearch`/`useStartFollowUp` invalidate, so
 * launching a job refreshes the library automatically. Offset paging: each page requests
 * `offset = loadedPages * PAGE_SIZE`; `getNextPageParam` stops once we've loaded `total` rows.
 */
export function useResearchHistory() {
  return useInfiniteQuery<JobListResponse>({
    queryKey: ['research', 'list'],
    queryFn: async ({ pageParam }) =>
      unwrapClientResult(
        await listResearchApiResearchGet({
          query: { limit: PAGE_SIZE, offset: pageParam as number },
        }),
      ),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const nextOffset = allPages.length * PAGE_SIZE
      return nextOffset < lastPage.total ? nextOffset : undefined
    },
  })
}
