import { useMutation } from '@tanstack/react-query'

import { unwrapClientResult } from '../services/api'
import { previewResearchApiResearchPreviewPost } from '../types/api'
import type { PreviewResponse, ResearchRequest } from '../types/api'

export function usePreviewResearch() {
  return useMutation({
    mutationFn: async (payload: ResearchRequest): Promise<PreviewResponse> => {
      // Translate the client's `{ data, error }` result into an ApiError so
      // callers can render rate-limit (429) and validation (422) details.
      return unwrapClientResult(await previewResearchApiResearchPreviewPost({ body: payload }))
    },
  })
}
