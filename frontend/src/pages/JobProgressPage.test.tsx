import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import JobProgressPage from './JobProgressPage'
import type { JobMessage, ConnectionStatus } from '../hooks/useJobStream'

// ——————————————————————————————————————————————————————————
// Module mocks (hoisted before imports resolve)
// ——————————————————————————————————————————————————————————

const mockNavigate = vi.fn()
const mockJobId = 'job-test-001'

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ jobId: mockJobId }),
  }
})

vi.mock('../hooks/useJobStream', () => ({
  useJobStream: vi.fn(),
}))

import { useJobStream } from '../hooks/useJobStream'

// ——————————————————————————————————————————————————————————
// Helpers
// ——————————————————————————————————————————————————————————

function stubStream(messages: JobMessage[], status: ConnectionStatus = 'open') {
  vi.mocked(useJobStream).mockReturnValue({ messages, status })
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <JobProgressPage />
    </QueryClientProvider>,
  )
}

const SNAPSHOT_SCOUTING: JobMessage = {
  type: 'snapshot',
  job_id: mockJobId,
  job: {
    id: mockJobId,
    topic: 'Why has CEE VC diverged from Western Europe?',
    status: 'scouting',
    created_at: new Date(Date.now() - 30_000).toISOString(),
  },
}

const SUB_QUESTIONS: JobMessage = {
  type: 'sub_questions_generated',
  job_id: mockJobId,
  sub_questions: ['How has deal volume changed?', 'Which LP types shifted allocation?'],
}

const SOURCE_FOUND: JobMessage = {
  type: 'source_found',
  job_id: mockJobId,
  source: {
    id: 'src-1',
    title: 'Dealroom Q1 2026',
    url: 'https://dealroom.co/report',
    credibility: 0.92,
    relevance: 0.88,
    snippet: 'CEE deal volume dropped 18% YoY.',
  },
}

const SECTION_DRAFTED: JobMessage = {
  type: 'section_drafted',
  job_id: mockJobId,
  section: {
    id: 'sec-1',
    heading: 'Executive Summary',
    body_md: 'The divergence is primarily driven by LP behaviour.',
    cited_source_ids: ['src-1'],
  },
}

const JOB_COMPLETED: JobMessage = {
  type: 'job_completed',
  job_id: mockJobId,
  overall_confidence: 0.87,
}

const JOB_FAILED: JobMessage = {
  type: 'job_failed',
  job_id: mockJobId,
  error: 'Scout timed out after 120 s',
}

// ——————————————————————————————————————————————————————————
// Tests
// ——————————————————————————————————————————————————————————

describe('JobProgressPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a connecting/loading state when the stream has no messages yet', () => {
    stubStream([], 'connecting')
    renderPage()

    // The topic placeholder shows while we wait for the snapshot.
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    // Brief bar is always present.
    expect(screen.getByText('Synapse')).toBeInTheDocument()
  })

  it('shows Scout phase as active after a snapshot with status scouting', () => {
    stubStream([SNAPSHOT_SCOUTING])
    renderPage()

    // Topic should appear in the brief bar.
    expect(screen.getByText(/"Why has CEE VC diverged from Western Europe\?"/)).toBeInTheDocument()

    // Scout card carries "Running now" badge.
    expect(screen.getAllByText('Running now').length).toBeGreaterThan(0)

    // Phase rail: Scout should be active (no ✓ check).
    // Check the pipeline section is rendered.
    expect(screen.getByLabelText('pipeline progress')).toBeInTheDocument()
  })

  it('renders the sub-questions after sub_questions_generated', () => {
    stubStream([SNAPSHOT_SCOUTING, SUB_QUESTIONS])
    renderPage()

    expect(screen.getByText('How has deal volume changed?')).toBeInTheDocument()
    expect(screen.getByText('Which LP types shifted allocation?')).toBeInTheDocument()
  })

  it('shows source pills after source_found events', () => {
    stubStream([SNAPSHOT_SCOUTING, SUB_QUESTIONS, SOURCE_FOUND])
    renderPage()

    // Source pills appear once per sub-question row since all sources are shown in each row.
    const pills = screen.getAllByText('Dealroom Q1 2026')
    expect(pills.length).toBeGreaterThan(0)
  })

  it('shows the section heading in the Scribe outline after section_drafted', () => {
    const scribingSnapshot: JobMessage = {
      type: 'snapshot',
      job_id: mockJobId,
      job: {
        id: mockJobId,
        topic: 'Why has CEE VC diverged?',
        status: 'synthesizing',
        created_at: new Date(Date.now() - 60_000).toISOString(),
      },
    }
    stubStream([scribingSnapshot, SECTION_DRAFTED])
    renderPage()

    expect(screen.getByText('Executive Summary')).toBeInTheDocument()
  })

  it('navigates to the report page after job_completed (with delay)', async () => {
    stubStream([SNAPSHOT_SCOUTING, JOB_COMPLETED])
    renderPage()

    // Before the delay fires, navigation should not have happened.
    expect(mockNavigate).not.toHaveBeenCalled()

    // Advance past the 1500ms redirect delay and flush pending React state updates.
    await act(async () => {
      vi.advanceTimersByTime(1600)
    })

    expect(mockNavigate).toHaveBeenCalledWith({
      to: '/research/$jobId/report',
      params: { jobId: mockJobId },
    })
  })

  it('shows the error message after job_failed and does not navigate', async () => {
    stubStream([SNAPSHOT_SCOUTING, JOB_FAILED])
    renderPage()

    // The brief bar status area shows the error.
    expect(screen.getByLabelText('job status')).toHaveTextContent(/Scout timed out/)

    // Advance past any would-be redirect delay to prove no navigation fires.
    await act(async () => {
      vi.advanceTimersByTime(3000)
    })

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('shows the connection-lost banner when WS status is error', () => {
    stubStream([SNAPSHOT_SCOUTING], 'error')
    renderPage()

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Connection lost — results may be incomplete.',
    )
  })

  it('shows the connection-lost banner when WS status is closed and job not terminal', () => {
    stubStream([SNAPSHOT_SCOUTING], 'closed')
    renderPage()

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Connection lost — results may be incomplete.',
    )
  })

  it('does not show connection-lost banner when job is completed even if socket closed', () => {
    stubStream([SNAPSHOT_SCOUTING, JOB_COMPLETED], 'closed')
    renderPage()

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('displays the elapsed timer label when stream is active', () => {
    stubStream([SNAPSHOT_SCOUTING])
    renderPage()

    // Timer label appears in the brief bar status section.
    expect(screen.getByLabelText('job status')).toHaveTextContent(/In progress/)
  })
})
