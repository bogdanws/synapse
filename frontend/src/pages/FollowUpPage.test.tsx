import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import FollowUpPage from './FollowUpPage'
import type { VerifiedReport } from '../types/api'

const mockJobId = 'parent-001'
const mockNavigate = vi.fn()

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useParams: () => ({ jobId: mockJobId }),
    useNavigate: () => mockNavigate,
    Link: ({
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => (
      <a {...props}>{children}</a>
    ),
  }
})

vi.mock('../hooks/useReport', () => ({ useReport: vi.fn() }))
vi.mock('../hooks/useStartFollowUp', () => ({ useStartFollowUp: vi.fn() }))

import { useReport } from '../hooks/useReport'
import { useStartFollowUp } from '../hooks/useStartFollowUp'

const mockReport = (followUps: string[]): VerifiedReport =>
  ({
    job: { id: mockJobId, status: 'completed' },
    report: {
      id: 'r1',
      job_id: mockJobId,
      title: 'Why has Eastern European VC diverged?',
      summary_md: '',
      sections: [],
      sources: [],
      contradictions: [],
      follow_ups: followUps,
      generated_at: new Date().toISOString(),
      model: 'm',
    },
    annotations: {},
  }) as unknown as VerifiedReport

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <FollowUpPage />
    </QueryClientProvider>,
  )
}

describe('FollowUpPage', () => {
  const mutate = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useStartFollowUp).mockReturnValue({
      mutate,
      isPending: false,
      error: null,
    } as unknown as ReturnType<typeof useStartFollowUp>)
  })

  it('shows the parent report title and the suggested follow-ups', () => {
    vi.mocked(useReport).mockReturnValue({
      data: mockReport(['What about funding stages?', 'How did exits fare?']),
      isLoading: false,
      error: null,
    })
    renderPage()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Why has Eastern European VC diverged?',
    )
    expect(screen.getByRole('button', { name: /What about funding stages/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /How did exits fare/i })).toBeInTheDocument()
  })

  it('clicking a suggestion fills the question field', async () => {
    vi.mocked(useReport).mockReturnValue({
      data: mockReport(['How did exits fare?']),
      isLoading: false,
      error: null,
    })
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /How did exits fare/i }))
    expect(screen.getByLabelText(/your question/i)).toHaveValue('How did exits fare?')
  })

  it('submits the question and navigates to the child progress view', async () => {
    mutate.mockImplementation(
      (_question: string, opts: { onSuccess: (child: { id: string }) => void }) => {
        opts.onSuccess({ id: 'child-009' })
      },
    )
    vi.mocked(useReport).mockReturnValue({
      data: mockReport([]),
      isLoading: false,
      error: null,
    })
    renderPage()

    await userEvent.type(screen.getByLabelText(/your question/i), 'What changed in 2024?')
    await userEvent.click(screen.getByRole('button', { name: /launch follow-up/i }))

    await waitFor(() => {
      expect(mutate).toHaveBeenCalledWith('What changed in 2024?', expect.anything())
      expect(mockNavigate).toHaveBeenCalledWith({
        to: '/research/$jobId',
        params: { jobId: 'child-009' },
      })
    })
  })

  it('does not submit an empty question', async () => {
    vi.mocked(useReport).mockReturnValue({
      data: mockReport([]),
      isLoading: false,
      error: null,
    })
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /launch follow-up/i }))

    expect(mutate).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent(/at least 3 characters/i)
  })
})
