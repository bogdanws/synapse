import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import ReportPage from './ReportPage'
import { ApiError } from '../services/api'
import type { VerifiedReport } from '../types/api'

// ——————————————————————————————————————————————————————————
// Module mocks
// ——————————————————————————————————————————————————————————

const mockJobId = 'test-job-001'

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useParams: () => ({ jobId: mockJobId }),
    Link: ({
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => (
      <a {...props}>{children}</a>
    ),
  }
})

vi.mock('../hooks/useReport', () => ({
  useReport: vi.fn(),
}))

vi.mock('../hooks/useJobLineage', () => ({
  useJobLineage: vi.fn(),
}))

import { useReport } from '../hooks/useReport'
import { useJobLineage } from '../hooks/useJobLineage'

// ——————————————————————————————————————————————————————————
// Fixtures
// ——————————————————————————————————————————————————————————

const _VERIFIED_REPORT: VerifiedReport = {
  job: {
    id: mockJobId,
    topic: 'Eastern European VC trends',
    language: 'en',
    depth: 'standard',
    models: { scout: 'gpt-4o', scribe: 'gpt-4o', critic: 'gpt-4o' },
    status: 'completed',
    progress: 1.0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
  },
  report: {
    id: 'report-001',
    job_id: mockJobId,
    topic: 'Eastern European VC trends',
    title: 'Why has Eastern European VC diverged?',
    summary_md: 'LP withdrawal, not founder behaviour, explains the gap.',
    sections: [
      {
        id: 'sec1',
        heading: 'The 2023 inflection',
        body_md: 'CEE deal volume fell <span data-claim="sec1.c1">41% YoY</span> in Q1 2023.',
        cited_source_ids: ['s1'],
      },
      {
        id: 'sec2',
        heading: 'LP Dynamics',
        body_md: 'U.S. and U.K. pension funds reduced commitments.',
        cited_source_ids: [],
      },
    ],
    sources: [
      {
        id: 's1',
        url: 'https://dealroom.co/report',
        title: 'Dealroom Q1 2026',
        credibility: 0.92,
        relevance: 0.88,
        snippet: 'CEE deal volume dropped 41% YoY.',
      },
    ],
    contradictions: [],
    follow_ups: [],
    generated_at: new Date().toISOString(),
    model: 'openai/gpt-4o',
  },
  annotations: {
    id: 'ann-001',
    report_id: 'report-001',
    section_confidence: [
      { section_id: 'sec1', score: 0.94, reasoning: 'Cross-checked against Dealroom.' },
    ],
    claim_flags: [
      {
        claim_id: 'sec1.c1',
        section_id: 'sec1',
        verdict: 'supported',
        rationale: 'Verified against Dealroom data.',
        supporting_source_ids: ['s1'],
      },
    ],
    overall_confidence: 0.92,
    model: 'openai/gpt-4o',
    generated_at: new Date().toISOString(),
  },
}

// ——————————————————————————————————————————————————————————
// Helpers
// ——————————————————————————————————————————————————————————

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ReportPage />
    </QueryClientProvider>,
  )
}

// ——————————————————————————————————————————————————————————
// Tests
// ——————————————————————————————————————————————————————————

describe('ReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default: no lineage. Individual cross-link tests override this.
    vi.mocked(useJobLineage).mockReturnValue({ data: undefined } as ReturnType<
      typeof useJobLineage
    >)
  })

  it('renders loading state while useReport is loading', () => {
    vi.mocked(useReport).mockReturnValue({ data: undefined, isLoading: true, error: null })
    renderPage()
    expect(screen.getByText(/loading report/i)).toBeInTheDocument()
  })

  it('renders the topic headline and summary when data is available', () => {
    vi.mocked(useReport).mockReturnValue({
      data: _VERIFIED_REPORT,
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Why has Eastern European VC diverged?',
    )
    expect(screen.getByText(/LP withdrawal, not founder behaviour/i)).toBeInTheDocument()
  })

  it('renders section headings', () => {
    vi.mocked(useReport).mockReturnValue({
      data: _VERIFIED_REPORT,
      isLoading: false,
      error: null,
    })
    renderPage()
    expect(screen.getByRole('heading', { name: /The 2023 inflection/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /LP Dynamics/i })).toBeInTheDocument()
  })

  it('renders claim spans with tooltip for flagged claims', () => {
    vi.mocked(useReport).mockReturnValue({
      data: _VERIFIED_REPORT,
      isLoading: false,
      error: null,
    })
    renderPage()
    // The claim text "41% YoY" is rendered inside a ClaimHighlight which wraps a Tooltip
    expect(screen.getByText(/41% YoY/i)).toBeInTheDocument()
  })

  it('shows "Report is being prepared" when the error is a 404', () => {
    vi.mocked(useReport).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new ApiError('not found', 404),
    })
    renderPage()
    expect(screen.getByText(/report is being prepared/i)).toBeInTheDocument()
    expect(screen.getByText(/back to progress view/i)).toBeInTheDocument()
  })

  it('renders a back-link to the parent when this report is a follow-up', () => {
    vi.mocked(useReport).mockReturnValue({
      data: _VERIFIED_REPORT,
      isLoading: false,
      error: null,
    })
    vi.mocked(useJobLineage).mockReturnValue({
      data: {
        parent: {
          job_id: 'parent-77',
          question: 'Original question',
          topic: 'The original Eastern European VC brief',
          status: 'completed',
          created_at: new Date().toISOString(),
        },
        children: [],
      },
    } as ReturnType<typeof useJobLineage>)
    renderPage()
    expect(screen.getByText(/Follow-up of/i)).toBeInTheDocument()
  })

  it('lists follow-up children with their status', () => {
    vi.mocked(useReport).mockReturnValue({
      data: _VERIFIED_REPORT,
      isLoading: false,
      error: null,
    })
    vi.mocked(useJobLineage).mockReturnValue({
      data: {
        parent: null,
        children: [
          {
            job_id: 'child-1',
            question: 'What about exits?',
            topic: 'What about exits?',
            status: 'completed',
            created_at: new Date().toISOString(),
          },
          {
            job_id: 'child-2',
            question: 'And funding stages?',
            topic: 'And funding stages?',
            status: 'scouting',
            created_at: new Date().toISOString(),
          },
        ],
      },
    } as ReturnType<typeof useJobLineage>)
    renderPage()
    expect(screen.getByText(/Follow-ups · 2/i)).toBeInTheDocument()
    expect(screen.getByText('What about exits?')).toBeInTheDocument()
    expect(screen.getByText('And funding stages?')).toBeInTheDocument()
    expect(screen.getByText('scouting')).toBeInTheDocument()
  })
})
