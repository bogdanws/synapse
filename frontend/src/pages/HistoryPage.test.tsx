import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import HistoryPage from './HistoryPage'
import type { JobSummary } from '../types/api'

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    Link: ({
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => (
      <a {...props}>{children}</a>
    ),
  }
})

vi.mock('../hooks/useResearchHistory', () => ({ useResearchHistory: vi.fn() }))
vi.mock('../hooks/useDeleteResearch', () => ({ useDeleteResearch: vi.fn() }))

import { useResearchHistory } from '../hooks/useResearchHistory'
import { useDeleteResearch } from '../hooks/useDeleteResearch'

const fetchNextPage = vi.fn()
const deleteMutate = vi.fn()

function mockHook(overrides: Record<string, unknown>) {
  vi.mocked(useResearchHistory).mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    fetchNextPage,
    hasNextPage: false,
    isFetchingNextPage: false,
    ...overrides,
  } as unknown as ReturnType<typeof useResearchHistory>)
}

function job(over: Partial<JobSummary> = {}): JobSummary {
  return {
    id: over.id ?? 'job-1',
    topic: over.topic ?? 'Why has Eastern European VC diverged?',
    status: over.status ?? 'completed',
    progress: over.progress ?? 1,
    created_at: over.created_at ?? new Date('2026-06-12').toISOString(),
    source_count: over.source_count ?? 14,
    overall_confidence: over.overall_confidence ?? 0.92,
    parent_job_id: over.parent_job_id ?? null,
    parent_topic: over.parent_topic ?? null,
  }
}

function page(items: JobSummary[], total = items.length) {
  return { data: { pages: [{ items, total, limit: 20, offset: 0 }] } }
}

describe('HistoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDeleteResearch).mockReturnValue({
      mutate: deleteMutate,
      isPending: false,
    } as unknown as ReturnType<typeof useDeleteResearch>)
  })

  it('shows a loading state', () => {
    mockHook({ isLoading: true })
    render(<HistoryPage />)
    expect(screen.getByText(/loading library/i)).toBeInTheDocument()
  })

  it('shows the empty state when there are no jobs', () => {
    mockHook(page([]))
    render(<HistoryPage />)
    expect(screen.getByText(/your library is empty/i)).toBeInTheDocument()
    expect(screen.getByText(/start a new brief/i)).toBeInTheDocument()
  })

  it('renders a completed job with status, source count and confidence', () => {
    mockHook(page([job()]))
    render(<HistoryPage />)
    expect(screen.getByText('Why has Eastern European VC diverged?')).toBeInTheDocument()
    expect(screen.getByText('completed')).toBeInTheDocument()
    expect(screen.getByText(/14 sources/i)).toBeInTheDocument()
    expect(screen.getByText(/92% confidence/i)).toBeInTheDocument()
  })

  it('renders a follow-up badge and a link to the parent', () => {
    mockHook(
      page([
        job({
          id: 'child-1',
          topic: 'What about exits?',
          parent_job_id: 'parent-9',
          parent_topic: 'The original brief',
        }),
      ]),
    )
    render(<HistoryPage />)
    expect(screen.getByText('↳ follow-up')).toBeInTheDocument()
    expect(screen.getByText(/Follow-up of/i)).toBeInTheDocument()
  })

  it('shows the in-progress status without confidence', () => {
    mockHook(page([job({ id: 'j2', status: 'scouting', overall_confidence: null })]))
    render(<HistoryPage />)
    expect(screen.getByText('scouting')).toBeInTheDocument()
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('renders "Load more" and calls fetchNextPage on click', async () => {
    mockHook({ ...page([job()], 25), hasNextPage: true })
    render(<HistoryPage />)
    const button = screen.getByRole('button', { name: /load more/i })
    await userEvent.click(button)
    expect(fetchNextPage).toHaveBeenCalledOnce()
  })

  it('asks for confirmation before deleting and does not delete on first click', async () => {
    mockHook(page([job()]))
    render(<HistoryPage />)
    await userEvent.click(screen.getByRole('button', { name: /delete why has eastern/i }))
    expect(screen.getByText('Delete?')).toBeInTheDocument()
    expect(deleteMutate).not.toHaveBeenCalled()
  })

  it('deletes the job when the confirmation is accepted', async () => {
    mockHook(page([job({ id: 'job-42' })]))
    render(<HistoryPage />)
    await userEvent.click(screen.getByRole('button', { name: /delete why has eastern/i }))
    await userEvent.click(screen.getByRole('button', { name: /^yes$/i }))
    expect(deleteMutate).toHaveBeenCalledWith('job-42')
  })

  it('cancels the confirmation without deleting', async () => {
    mockHook(page([job()]))
    render(<HistoryPage />)
    await userEvent.click(screen.getByRole('button', { name: /delete why has eastern/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByText('Delete?')).not.toBeInTheDocument()
    expect(deleteMutate).not.toHaveBeenCalled()
  })
})
