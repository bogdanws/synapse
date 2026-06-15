import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'

import { useStartFollowUp } from './useStartFollowUp'
import { startFollowUpApiResearchJobIdFollowUpPost } from '../types/api'
import { ApiError } from '../services/api'

vi.mock('../types/api', () => ({
  startFollowUpApiResearchJobIdFollowUpPost: vi.fn(),
}))

const mockPost = vi.mocked(startFollowUpApiResearchJobIdFollowUpPost)

function wrapper(queryClient: QueryClient) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe('useStartFollowUp', () => {
  beforeEach(() => {
    mockPost.mockReset()
  })

  it('posts the question to the parent job and returns the child job', async () => {
    const child = { id: 'child-1', topic: 'What about X?', status: 'pending' }
    mockPost.mockResolvedValue({ data: child, response: { status: 202 } } as never)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useStartFollowUp('parent-1'), {
      wrapper: wrapper(queryClient),
    })

    const returned = await result.current.mutateAsync('What about X?')

    expect(returned).toEqual(child)
    expect(mockPost).toHaveBeenCalledWith({
      path: { job_id: 'parent-1' },
      body: { question: 'What about X?' },
    })
  })

  it('throws an ApiError carrying the status when the parent is not completed', async () => {
    mockPost.mockResolvedValue({
      error: { detail: 'Only a completed report can be followed up.' },
      response: { status: 409 },
    } as never)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useStartFollowUp('parent-1'), {
      wrapper: wrapper(queryClient),
    })

    await expect(result.current.mutateAsync('Q?')).rejects.toBeInstanceOf(ApiError)
  })

  it('invalidates the list and parent lineage on success', async () => {
    mockPost.mockResolvedValue({
      data: { id: 'child-1' },
      response: { status: 202 },
    } as never)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useStartFollowUp('parent-1'), {
      wrapper: wrapper(queryClient),
    })

    await result.current.mutateAsync('Q?')

    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research', 'list'] })
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['research', 'parent-1', 'lineage'] })
    })
  })
})
