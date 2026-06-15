import { useMutation, useQueryClient } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { deleteResearchApiResearchJobIdDelete } from '../types/api'

/*
 * Delete one of the caller's research jobs (DELETE /api/research/{job_id}).
 *
 * Invalidates `['research', 'list']` so the library refreshes without the deleted brief. Follow-up
 * children are not removed server-side — only the parent/child link — so they keep appearing as
 * standalone briefs in the list.
 */
export function useDeleteResearch() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (jobId: string): Promise<void> => {
      // unwrapClientResult turns the client's `{ data, error }` into a thrown ApiError on failure
      // (e.g. 404 for a brief that's already gone), so the UI can react.
      unwrapClientResult(await deleteResearchApiResearchJobIdDelete({ path: { job_id: jobId } }))
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['research', 'list'] })
    },
  })
}
