import { describe, expect, it } from 'vitest'

import { previewStateSchema } from './researchPreviewState'

const validPreviewState = {
  formData: {
    topic: 'Why has Eastern European venture funding declined?',
    depth: 'standard' as const,
    language: 'en',
    models: {
      scout: 'openrouter/free',
      scribe: 'openrouter/free',
      critic: 'openrouter/free',
    },
  },
  subQuestions: ['How did exits change in 2024?'],
}

describe('previewStateSchema', () => {
  it('accepts router state pushed from the research input form', () => {
    expect(previewStateSchema.safeParse(validPreviewState).success).toBe(true)
  })

  it('rejects a direct URL hit with no preview plan', () => {
    expect(previewStateSchema.safeParse(undefined).success).toBe(false)
    expect(previewStateSchema.safeParse({}).success).toBe(false)
    expect(previewStateSchema.safeParse({ formData: validPreviewState.formData }).success).toBe(
      false,
    )
  })

  it('rejects an empty sub-question list', () => {
    const result = previewStateSchema.safeParse({
      ...validPreviewState,
      subQuestions: [],
    })
    expect(result.success).toBe(false)
  })
})
