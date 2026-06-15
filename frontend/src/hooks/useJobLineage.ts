import { useQuery } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { getJobLineageApiResearchJobIdLineageGet } from '../types/api'
import type { JobLineage } from '../types/api'

const _TERMINAL = new Set(['completed', 'failed'])

export function useJobLineage(jobId: string) {
  return useQuery({
    queryKey: ['research', jobId, 'lineage'],
    queryFn: async (): Promise<JobLineage> => {
      return unwrapClientResult(
        await getJobLineageApiResearchJobIdLineageGet({ path: { job_id: jobId } }),
      )
    },
    retry: false,
    // A freshly-spawned child is still running; poll so its status (and the
    // cross-link target) settles on the parent's report without a manual reload.
    // Stop once every child has reached a terminal state.
    refetchInterval: (query) => {
      const lineage = query.state.data
      if (!lineage) return false
      const anyInFlight = lineage.children.some((c) => !_TERMINAL.has(c.status))
      return anyInFlight ? 5000 : false
    },
  })
}
