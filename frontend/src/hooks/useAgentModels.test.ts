import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import { useAgentModels } from './useAgentModels'
import { DEFAULT_AGENT_MODELS, MODEL_STORAGE_KEY } from '../constants/models'

const storage: Record<string, string> = {}

const localStorageMock = {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => {
    storage[key] = value
  },
  removeItem: (key: string) => {
    delete storage[key]
  },
  clear: () => {
    Object.keys(storage).forEach((k) => delete storage[k])
  },
  length: 0,
  key: () => null,
}

vi.stubGlobal('localStorage', localStorageMock)

describe('useAgentModels', () => {
  beforeEach(() => {
    localStorageMock.clear()
  })

  it('returns defaults when localStorage is empty', () => {
    const { result } = renderHook(() => useAgentModels())
    expect(result.current.models).toEqual(DEFAULT_AGENT_MODELS)
  })

  it('returns persisted values when localStorage has a valid payload', () => {
    const stored = {
      scout: 'openai/gpt-4o-mini',
      scribe: 'deepseek/deepseek-v4-pro',
      critic: 'qwen/qwen3.7-plus',
    }
    localStorage.setItem(MODEL_STORAGE_KEY, JSON.stringify(stored))

    const { result } = renderHook(() => useAgentModels())
    expect(result.current.models).toEqual(stored)
  })

  it('falls back to defaults when localStorage is a plain string', () => {
    localStorage.setItem(MODEL_STORAGE_KEY, 'not-json')
    const { result } = renderHook(() => useAgentModels())
    expect(result.current.models).toEqual(DEFAULT_AGENT_MODELS)
  })

  it('falls back to defaults when keys are missing', () => {
    localStorage.setItem(MODEL_STORAGE_KEY, JSON.stringify({ scout: 'openrouter/free' }))
    const { result } = renderHook(() => useAgentModels())
    expect(result.current.models).toEqual(DEFAULT_AGENT_MODELS)
  })

  it('falls back to defaults when a model id is invalid', () => {
    localStorage.setItem(
      MODEL_STORAGE_KEY,
      JSON.stringify({
        scout: 'openrouter/free',
        scribe: 'openrouter/free',
        critic: 'evil/model',
      }),
    )
    const { result } = renderHook(() => useAgentModels())
    expect(result.current.models).toEqual(DEFAULT_AGENT_MODELS)
  })

  it('persist writes current state to localStorage', () => {
    const { result } = renderHook(() => useAgentModels())

    act(() => {
      result.current.setModel('scout', 'openai/gpt-4o-mini')
    })

    act(() => {
      result.current.persist()
    })

    const stored = JSON.parse(localStorage.getItem(MODEL_STORAGE_KEY) ?? '{}')
    expect(stored).toEqual({
      scout: 'openai/gpt-4o-mini',
      scribe: 'openrouter/free',
      critic: 'openrouter/free',
    })
  })
})
