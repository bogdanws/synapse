import { useQuery } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { getReportApiResearchJobIdReportGet } from '../types/api'
import type { VerifiedReport } from '../types/api'

export function useReport(jobId: string): {
  data: VerifiedReport | undefined
  isLoading: boolean
  error: Error | null
} {
  const { data, isLoading, error } = useQuery({
    queryKey: ['research', jobId, 'report'],
    queryFn: async (): Promise<VerifiedReport> => {
      // Throwing on non-2xx lets React Query distinguish "not ready" (404)
      // from genuine errors. ReportPage discriminates on `error.status`.
      return unwrapClientResult(
        await getReportApiResearchJobIdReportGet({ path: { job_id: jobId } }),
      )
    },
    retry: false,
  })

  return {
    data,
    isLoading,
    error,
  }
}
