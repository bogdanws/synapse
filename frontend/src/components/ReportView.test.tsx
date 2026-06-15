import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import { ReportView } from './ReportView'
import type { VerifiedReport } from '../types/api'

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

const reportFixture: VerifiedReport = {
  job: {
    id: 'job-src-order',
    topic: 'Source ordering check',
    language: 'en',
    depth: 'standard',
    models: { scout: 'gpt-4o', scribe: 'gpt-4o', critic: 'gpt-4o' },
    status: 'completed',
    progress: 1,
    created_at: '2026-06-01T12:00:00.000Z',
    updated_at: '2026-06-01T12:30:00.000Z',
    completed_at: '2026-06-01T12:30:00.000Z',
  },
  report: {
    id: 'report-src-order',
    job_id: 'job-src-order',
    topic: 'Source ordering check',
    title: 'Source ordering check',
    summary_md: 'Summary.',
    sections: [
      {
        id: 'sec1',
        heading: 'Evidence',
        body_md: 'First claim.',
        cited_source_ids: ['s-low', 's-high'],
      },
    ],
    // Backend order is relevance-ranked; the panel should preserve it.
    sources: [
      {
        id: 's-high',
        url: 'https://high.example.com',
        title: 'High relevance source',
        credibility: 0.9,
        relevance: 0.95,
        snippet: 'Most relevant.',
      },
      {
        id: 's-low',
        url: 'https://low.example.com',
        title: 'Lower relevance source',
        credibility: 0.7,
        relevance: 0.4,
        snippet: 'Less relevant.',
      },
    ],
    contradictions: [],
    follow_ups: [],
    generated_at: '2026-06-01T12:30:00.000Z',
    model: 'gpt-4o',
  },
  annotations: {
    id: 'ann-src-order',
    report_id: 'report-src-order',
    section_confidence: [{ section_id: 'sec1', score: 0.88, reasoning: 'Solid.' }],
    claim_flags: [
      {
        claim_id: 'sec1.c1',
        section_id: 'sec1',
        verdict: 'supported',
        rationale: 'Backed by the top source.',
        supporting_source_ids: ['s-high'],
      },
    ],
    overall_confidence: 0.88,
    model: 'gpt-4o',
    generated_at: '2026-06-01T12:30:00.000Z',
  },
}

describe('ReportView source panel', () => {
  it('lists sources in backend order with stable citation indices', () => {
    render(<ReportView data={reportFixture} jobId="job-src-order" />)

    const list = screen.getByRole('list')
    const rows = list.querySelectorAll('.source-row')

    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveAttribute('id', 's-high')
    expect(rows[0]).toHaveTextContent('[1] High relevance source')
    expect(rows[1]).toHaveAttribute('id', 's-low')
    expect(rows[1]).toHaveTextContent('[2] Lower relevance source')
  })

  it('surfaces section confidence and VERIFIED badges in the margin rail', () => {
    render(<ReportView data={reportFixture} jobId="job-src-order" />)

    expect(screen.getByText('.88')).toBeInTheDocument()
    expect(screen.getByText('VERIFIED')).toBeInTheDocument()
    expect(screen.getByText('Backed by the top source.')).toBeInTheDocument()
  })
})
