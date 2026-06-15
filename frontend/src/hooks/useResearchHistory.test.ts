import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../types/api', () => ({
  listResearchApiResearchGet: vi.fn(),
}))
vi.mock('../services/api', () => ({
  unwrapClientResult: (r: { data?: unknown; error?: unknown }) => r.data,
}))

import { useResearchHistory } from './useResearchHistory'
import { listResearchApiResearchGet } from '../types/api'

const mockList = vi.mocked(listResearchApiResearchGet)

function makeItem(id: string) {
  return {
    id,
    topic: `Topic ${id}`,
    status: 'completed' as const,
    progress: 1,
    created_at: new Date().toISOString(),
    source_count: 3,
    overall_confidence: 0.9,
    parent_job_id: null,
    parent_topic: null,
  }
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client }, children)
}

describe('useResearchHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches the first page with offset 0', async () => {
    mockList.mockResolvedValue({
      data: { items: [makeItem('a')], total: 1, limit: 20, offset: 0 },
    } as unknown as Awaited<ReturnType<typeof listResearchApiResearchGet>>)

    const { result } = renderHook(() => useResearchHistory(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockList).toHaveBeenCalledWith({ query: { limit: 20, offset: 0 } })
    expect(result.current.data?.pages[0]?.items).toHaveLength(1)
    expect(result.current.hasNextPage).toBe(false)
  })

  it('merges pages and stops at total via fetchNextPage', async () => {
    // 25 total: first page 20 items, second page 5.
    mockList.mockImplementation((opts) => {
      const offset = (opts?.query?.offset ?? 0) as number
      const items = Array.from({ length: offset === 0 ? 20 : 5 }, (_, i) =>
        makeItem(`${offset + i}`),
      )
      return Promise.resolve({
        data: { items, total: 25, limit: 20, offset },
      }) as unknown as ReturnType<typeof listResearchApiResearchGet>
    })

    const { result } = renderHook(() => useResearchHistory(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.hasNextPage).toBe(true)

    await result.current.fetchNextPage()

    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2))
    expect(mockList).toHaveBeenLastCalledWith({ query: { limit: 20, offset: 20 } })
    const all = result.current.data?.pages.flatMap((p) => p.items) ?? []
    expect(all).toHaveLength(25)
    expect(result.current.hasNextPage).toBe(false)
  })
})
