import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ResearchInputPage from './ResearchInputPage'

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

  it('fills topic when clicking an example question', async () => {
    renderPage()

    const example = screen.getByText(/current state of evidence on GLP-1 agonists/i)
    await userEvent.click(example)

    const textarea = screen.getByPlaceholderText(
      /type your research topic here/i,
    ) as HTMLTextAreaElement
    expect(textarea.value).toBe(
      "What's the current state of evidence on GLP-1 agonists and cardiovascular outcomes in non-diabetic patients?",
    )
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
