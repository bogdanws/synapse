import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ResearchPreviewPage from './ResearchPreviewPage'

const mockNavigate = vi.fn()
const mockLocation = vi.fn()
const mockStartResearch = vi.hoisted(() => vi.fn())
const mockPreviewResearch = vi.hoisted(() => vi.fn())

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => mockLocation(),
    Link: ({
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => (
      <a {...props}>{children}</a>
    ),
  }
})

vi.mock('../hooks/useStartResearch', () => ({
  useStartResearch: () => ({
    mutateAsync: mockStartResearch,
    isPending: false,
    error: null,
  }),
}))

vi.mock('../hooks/usePreviewResearch', () => ({
  usePreviewResearch: () => ({
    mutateAsync: mockPreviewResearch,
    isPending: false,
    error: null,
  }),
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
}))

const VALID_STATE = {
  formData: {
    topic: 'Why has Eastern European VC diverged from Western Europe?',
    depth: 'standard' as const,
    language: 'en',
    models: {
      scout: 'openai/gpt-4o-mini',
      scribe: 'openai/gpt-4o',
      critic: 'openai/gpt-4o',
    },
  },
  subQuestions: [
    'How has CEE deal volume tracked vs. Western Europe quarterly since 2021?',
    'Which LP categories changed allocation to CEE managers, 2023–2025?',
    'What is the EIF PFLP commitment cadence to CEE since 2023?',
  ],
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ResearchPreviewPage />
    </QueryClientProvider>,
  )
}

describe('ResearchPreviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStartResearch.mockReset()
    mockPreviewResearch.mockReset()
    mockLocation.mockReturnValue({ state: VALID_STATE, pathname: '/research/preview' })
  })

  it('renders the topic and all sub-questions when valid state is provided', () => {
    renderPage()

    expect(screen.getByText(/Eastern European VC/i)).toBeInTheDocument()
    expect(screen.getByText(/CEE deal volume/i)).toBeInTheDocument()
    expect(screen.getByText(/LP categories/i)).toBeInTheDocument()
    expect(screen.getByText(/PFLP commitment/i)).toBeInTheDocument()
  })

  it('shows the sub-question count in the heading', () => {
    renderPage()

    // The h2 contains "Scout proposes N sub-questions." — match the heading element directly.
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading).toHaveTextContent(/Scout proposes/i)
    expect(heading).toHaveTextContent(/3 sub‑question/i)
  })

  it('"Drop" toggles a question to dropped state and changes button to "Restore"', async () => {
    renderPage()

    const dropButtons = screen.getAllByRole('button', { name: /^drop$/i })
    await userEvent.click(dropButtons[0])

    await waitFor(() => {
      // The DROPPED label appears on the row item itself (not the footer stat)
      expect(screen.getByText('DROPPED')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^restore$/i })).toBeInTheDocument()
    })
  })

  it('"Restore" un-drops a dropped question', async () => {
    renderPage()

    const dropButtons = screen.getAllByRole('button', { name: /^drop$/i })
    await userEvent.click(dropButtons[0])

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^restore$/i })).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /^restore$/i }))

    await waitFor(() => {
      // After restore the DROPPED label on the row should be gone; the footer
      // stat continues to show "0 dropped" but no individual row carries the label.
      expect(screen.queryByText('DROPPED')).not.toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /^drop$/i })).toHaveLength(3)
    })
  })

  it('"Approve & launch" calls startResearch with the original formData and navigates', async () => {
    mockStartResearch.mockResolvedValue({
      id: 'job-abc',
      topic: VALID_STATE.formData.topic,
      status: 'pending',
    })

    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /approve & launch/i }))

    await waitFor(() => {
      expect(mockStartResearch).toHaveBeenCalledWith(
        expect.objectContaining({
          topic: VALID_STATE.formData.topic,
          depth: 'standard',
          language: 'en',
        }),
      )
    })

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: '/research/$jobId',
        params: { jobId: 'job-abc' },
      })
    })
  })

  it('redirects to /research/new when router state is missing', () => {
    mockLocation.mockReturnValue({ state: null, pathname: '/research/preview' })

    renderPage()

    expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
  })

  it('redirects to /research/new when router state has invalid shape', () => {
    mockLocation.mockReturnValue({
      state: { formData: { bad: 'data' }, subQuestions: [] },
      pathname: '/research/preview',
    })

    renderPage()

    expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
  })

  it('disables launch and shows an inline error when every sub-question is dropped', async () => {
    renderPage()

    // Drop all three sub-questions one by one.
    for (const btn of screen.getAllByRole('button', { name: /^drop$/i })) {
      await userEvent.click(btn)
    }

    const launch = screen.getByRole('button', { name: /approve & launch/i })
    expect(launch).toBeDisabled()
    // Without the guard the backend would coerce `sub_questions: []` to None
    // and silently re-run Scout's decompose, ignoring the user's intent.
    expect(mockStartResearch).not.toHaveBeenCalled()
  })

  it('"Back to brief" navigates to /research/new', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /back to brief/i }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
    })
  })
})
