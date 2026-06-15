import { describe, expect, it } from 'vitest'

import { ALLOWED_MODELS } from '../constants/models'
import { researchFormSchema } from './researchFormSchema'

const validModels = {
  scout: 'openrouter/free',
  scribe: 'openrouter/free',
  critic: 'openrouter/free',
}

const validPayload = {
  topic: 'Why has Eastern European venture funding declined?',
  depth: 'standard' as const,
  language: 'en',
  models: validModels,
}

describe('researchFormSchema', () => {
  it('accepts a well-formed payload at the boundaries', () => {
    expect(researchFormSchema.safeParse(validPayload).success).toBe(true)
    expect(
      researchFormSchema.safeParse({
        ...validPayload,
        topic: 'a'.repeat(10),
      }).success,
    ).toBe(true)
    expect(
      researchFormSchema.safeParse({
        ...validPayload,
        topic: 'a'.repeat(2000),
      }).success,
    ).toBe(true)
  })

  it('rejects topics shorter than 10 characters', () => {
    const result = researchFormSchema.safeParse({
      ...validPayload,
      topic: 'too short',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe('Topic must be at least 10 characters')
    }
  })

  it('rejects topics longer than 2000 characters', () => {
    const result = researchFormSchema.safeParse({
      ...validPayload,
      topic: 'a'.repeat(2001),
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0]?.code).toBe('too_big')
    }
  })

  it('rejects unknown depth values', () => {
    const result = researchFormSchema.safeParse({
      ...validPayload,
      depth: 'exhaustive',
    })
    expect(result.success).toBe(false)
  })

  it('accepts each allowed depth', () => {
    for (const depth of ['shallow', 'standard', 'deep'] as const) {
      expect(researchFormSchema.safeParse({ ...validPayload, depth }).success).toBe(true)
    }
  })

  it('rejects model IDs outside the allow-list', () => {
    const result = researchFormSchema.safeParse({
      ...validPayload,
      models: { ...validModels, scout: 'vendor/rogue-model' },
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0]?.message).toBe('Invalid model selection')
    }
  })

  it('accepts every model from ALLOWED_MODELS', () => {
    for (const model of ALLOWED_MODELS) {
      const result = researchFormSchema.safeParse({
        ...validPayload,
        models: {
          scout: model.id,
          scribe: model.id,
          critic: model.id,
        },
      })
      expect(result.success).toBe(true)
    }
  })
})
