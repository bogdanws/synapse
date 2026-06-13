import { useQuery } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { getJobLineageApiResearchJobIdLineageGet } from '../types/api'
import type { JobLineage } from '../types/api'

export function useJobLineage(jobId: string) {
  return useQuery({
    queryKey: ['research', jobId, 'lineage'],
    queryFn: async (): Promise<JobLineage> => {
      return unwrapClientResult(
        await getJobLineageApiResearchJobIdLineageGet({ path: { job_id: jobId } }),
      )
    },
    retry: false,
  })
}
