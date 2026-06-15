import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../types/api', () => ({
  deleteResearchApiResearchJobIdDelete: vi.fn(),
}))
vi.mock('../services/api', () => ({
  unwrapClientResult: (r: { data?: unknown; error?: unknown }) => {
    if (r.error) throw r.error
    return r.data
  },
}))

import { useDeleteResearch } from './useDeleteResearch'
import { deleteResearchApiResearchJobIdDelete } from '../types/api'

const mockDelete = vi.mocked(deleteResearchApiResearchJobIdDelete)

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client }, children)
}

describe('useDeleteResearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls DELETE with the job id in the path', async () => {
    mockDelete.mockResolvedValue({ data: undefined } as never)
    const { result } = renderHook(() => useDeleteResearch(), { wrapper })

    result.current.mutate('job-77')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockDelete).toHaveBeenCalledWith({ path: { job_id: 'job-77' } })
  })

  it('surfaces an error when the client returns one', async () => {
    mockDelete.mockResolvedValue({ error: new Error('gone') } as never)
    const { result } = renderHook(() => useDeleteResearch(), { wrapper })

    result.current.mutate('missing')

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
