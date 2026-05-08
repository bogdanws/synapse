import { useMutation } from '@tanstack/react-query'

import { previewResearchApiResearchPreviewPost } from '../types/api'
import type { PreviewResponse, ResearchRequest } from '../types/api'

export function usePreviewResearch() {
  return useMutation({
    mutationFn: async (payload: ResearchRequest): Promise<PreviewResponse> => {
      const result = await previewResearchApiResearchPreviewPost({ body: payload })
      if (!result.data) {
        throw new Error('Preview returned no data')
      }
      return result.data
    },
  })
}
