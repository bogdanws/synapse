import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ResearchInputPage from './ResearchInputPage'
import type { JobSummary } from '../types/api'

const mockNavigate = vi.fn()
const mockStartResearch = vi.hoisted(() => vi.fn())

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

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    Link: ({
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => (
      <a {...props}>{children}</a>
    ),
  }
})

vi.mock('../hooks/useMe', () => ({
  useMe: () => ({ email: 'alice@example.com', id: '1', is_active: true }),
}))

vi.mock('../hooks/useResearchHistory', () => ({ useResearchHistory: vi.fn() }))

import { useResearchHistory } from '../hooks/useResearchHistory'

function mockHistory(
  jobs: Array<{ topic: string; followUps?: string[]; status?: JobSummary['status'] }>,
) {
  const items = jobs.map(
    (job, i): JobSummary => ({
      id: `job-${i}`,
      topic: job.topic,
      status: job.status ?? 'completed',
      progress: 1,
      created_at: new Date('2026-06-12').toISOString(),
      source_count: 8,
      overall_confidence: 0.9,
      parent_job_id: null,
      parent_topic: null,
      follow_ups: job.followUps ?? [],
    }),
  )
  vi.mocked(useResearchHistory).mockReturnValue({
    data: { pages: [{ items, total: items.length, limit: 20, offset: 0 }] },
  } as unknown as ReturnType<typeof useResearchHistory>)
}

vi.mock('../services/api', () => ({
  ApiError: class ApiError extends Error {
    readonly status: number
    constructor(message: string, status: number) {
      super(message)
      this.name = 'ApiError'
      this.status = status
    }
  },
  api: {
    startResearch: mockStartResearch,
  },
}))

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ResearchInputPage />
    </QueryClientProvider>,
  )
}

describe('ResearchInputPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    mockStartResearch.mockReset()
    mockHistory([])
  })

  it('renders headline, textarea, and agent model pills', () => {
    renderPage()

    expect(screen.getByText(/what would you like/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/type your research topic here/i)).toBeInTheDocument()
    expect(screen.getByText('Scout')).toBeInTheDocument()
    expect(screen.getByText('Scribe')).toBeInTheDocument()
    expect(screen.getByText('Critic')).toBeInTheDocument()
  })

  it('shows validation error when submitting empty topic', async () => {
    renderPage()

    const button = screen.getByRole('button', { name: /start brief/i })
    await userEvent.click(button)

    await waitFor(() => {
      expect(screen.getByText(/topic must be at least 10 characters/i)).toBeInTheDocument()
    })
  })

  it('calls mutation with correct defaults and navigates on success', async () => {
    mockStartResearch.mockResolvedValue({
      id: 'job-123',
      topic: 'Test topic',
      status: 'pending',
    })

    renderPage()

    const textarea = screen.getByPlaceholderText(/type your research topic here/i)
    await userEvent.type(textarea, 'Why has Eastern European venture funding declined?')

    const button = screen.getByRole('button', { name: /start brief/i })
    await userEvent.click(button)

    await waitFor(() => {
      expect(mockStartResearch).toHaveBeenCalledWith({
        topic: 'Why has Eastern European venture funding declined?',
        depth: 'standard',
        language: 'en',
        models: {
          scout: 'openrouter/free',
          scribe: 'openrouter/free',
          critic: 'openrouter/free',
        },
      })
    })

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: '/research/$jobId',
        params: { jobId: 'job-123' },
      })
    })
  })

  it('renders server error inline for 422', async () => {
    const { ApiError } = await import('../services/api')
    mockStartResearch.mockRejectedValue(new ApiError('Request failed: 422 — Invalid topic', 422))

    renderPage()

    const textarea = screen.getByPlaceholderText(/type your research topic here/i)
    await userEvent.type(textarea, 'Why has Eastern European venture funding declined?')

    const button = screen.getByRole('button', { name: /start brief/i })
    await userEvent.click(button)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid topic/i)
    })
  })

  it('renders server error inline for 429', async () => {
    const { ApiError } = await import('../services/api')
    mockStartResearch.mockRejectedValue(
      new ApiError('Request failed: 429 — Rate limit exceeded', 429),
    )

    renderPage()

    const textarea = screen.getByPlaceholderText(/type your research topic here/i)
    await userEvent.type(textarea, 'Why has Eastern European venture funding declined?')

    const button = screen.getByRole('button', { name: /start brief/i })
    await userEvent.click(button)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/rate limit exceeded/i)
    })
  })

  it('seeds the recent-question grid from report follow-ups and fills the topic on click', async () => {
    mockHistory([
      {
        topic: 'Why has Eastern European venture funding declined?',
        followUps: ['How did exits change in 2024?'],
      },
    ])
    renderPage()

    const example = screen.getByRole('button', {
      name: /How did exits change in 2024\?/i,
    })
    await userEvent.click(example)

    const textarea = screen.getByPlaceholderText(
      /type your research topic here/i,
    ) as HTMLTextAreaElement
    expect(textarea.value).toBe('How did exits change in 2024?')
  })

  it('hides the recent-question grid when history has no follow-up suggestions', () => {
    mockHistory([{ topic: 'Completed brief with no suggestions', followUps: [] }])
    renderPage()

    expect(screen.queryByText(/start from a recent question/i)).not.toBeInTheDocument()
  })

  it('round-robins one follow-up per report before taking another from the same report', () => {
    mockHistory([
      { topic: 'Newest brief', followUps: ['A-first', 'A-second'] },
      { topic: 'Middle brief', followUps: ['B-first'] },
      { topic: 'Oldest brief', followUps: ['C-first', 'C-second'] },
    ])
    renderPage()

    const grid = screen.getByText(/start from a recent question/i).parentElement!
    const labels = Array.from(grid.querySelectorAll('button .serif')).map((el) => el.textContent)
    expect(labels).toEqual(['A-first', 'B-first', 'C-first', 'A-second'])
  })

  it('uses persisted model selections from localStorage', async () => {
    localStorage.setItem(
      'synapse:agent-models:v1',
      JSON.stringify({
        scout: 'openai/gpt-4o-mini',
        scribe: 'deepseek/deepseek-v4-pro',
        critic: 'qwen/qwen3.7-plus',
      }),
    )

    mockStartResearch.mockResolvedValue({
      id: 'job-456',
      topic: 'Test',
      status: 'pending',
    })

    renderPage()

    const textarea = screen.getByPlaceholderText(/type your research topic here/i)
    await userEvent.type(textarea, 'Why has Eastern European venture funding declined?')

    const button = screen.getByRole('button', { name: /start brief/i })
    await userEvent.click(button)

    await waitFor(() => {
      expect(mockStartResearch).toHaveBeenCalledWith(
        expect.objectContaining({
          models: {
            scout: 'openai/gpt-4o-mini',
            scribe: 'deepseek/deepseek-v4-pro',
            critic: 'qwen/qwen3.7-plus',
          },
        }),
      )
    })
  })
})
