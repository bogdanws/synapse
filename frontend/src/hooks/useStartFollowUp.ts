import { useMutation, useQueryClient } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { startFollowUpApiResearchJobIdFollowUpPost } from '../types/api'
import type { ResearchJob } from '../types/api'

export function useStartFollowUp(parentJobId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (question: string): Promise<ResearchJob> => {
      // Translate the client's `{ data, error }` result into an ApiError so the
      // page can surface rate-limit (429), validation (422), and 409 (parent not
      // completed) details.
      return unwrapClientResult(
        await startFollowUpApiResearchJobIdFollowUpPost({
          path: { job_id: parentJobId },
          body: { question },
        }),
      )
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['research', 'list'] })
      // The parent now has a new child; refresh its lineage so the report's
      // follow-up list reflects it on next view.
      queryClient.invalidateQueries({ queryKey: ['research', parentJobId, 'lineage'] })
    },
  })
}
