import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ReportRenderer } from './ReportRenderer'
import { TooltipProvider } from './ui/Tooltip'
import type { ClaimFlag, ReportSection, Source } from '../types/api'

const sources: Source[] = [
  {
    id: 's1',
    url: 'https://dealroom.co/report',
    title: 'Dealroom Q1 2026',
    credibility: 0.92,
    relevance: 0.88,
    snippet: 'CEE deal volume dropped 41% YoY.',
  },
]

function renderRenderer(
  body_md: string,
  claimFlags: ClaimFlag[] = [],
  extraSources: Source[] = sources,
) {
  const section: ReportSection = {
    id: 'sec1',
    heading: 'Section',
    body_md,
    cited_source_ids: extraSources.map((s) => s.id),
  }

  return render(
    <TooltipProvider>
      <ReportRenderer section={section} claimFlags={claimFlags} sources={extraSources} />
    </TooltipProvider>,
  )
}

describe('ReportRenderer', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockImplementation(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    )
  })

  it('applies verdict-specific highlight classes to flagged claims', () => {
    const claimFlags: ClaimFlag[] = [
      {
        claim_id: 'sec1.c1',
        section_id: 'sec1',
        verdict: 'supported',
        rationale: 'Cross-checked against Dealroom.',
        supporting_source_ids: ['s1'],
      },
    ]

    const { container } = renderRenderer(
      'Volume fell <span data-claim="sec1.c1">41% YoY</span>.',
      claimFlags,
    )

    const claim = container.querySelector('[data-claim="sec1.c1"]')
    expect(claim).toHaveClass('bg-scout-soft')
    expect(claim).not.toHaveClass('line-through')
  })

  it('strikes through contradicted claims', () => {
    const claimFlags: ClaimFlag[] = [
      {
        claim_id: 'sec1.c1',
        section_id: 'sec1',
        verdict: 'contradicted',
        rationale: 'Sources disagree on direction.',
        supporting_source_ids: ['s1'],
      },
    ]

    const { container } = renderRenderer(
      'Revenue grew <span data-claim="sec1.c1">300%</span>.',
      claimFlags,
    )

    const claim = container.querySelector('[data-claim="sec1.c1"]')
    expect(claim).toHaveClass('bg-critic-soft', 'line-through')
  })

  it('leaves unflagged claim spans unstyled', () => {
    const { container } = renderRenderer('Plain <span data-claim="sec1.c9">claim</span> text.')

    const claim = container.querySelector('[data-claim="sec1.c9"]')
    expect(claim).not.toHaveClass('bg-scout-soft')
    expect(claim).not.toHaveClass('bg-scribe-soft')
    expect(claim).not.toHaveClass('bg-critic-soft')
  })

  it('shows the critic rationale in the claim tooltip on hover', async () => {
    const user = userEvent.setup()
    const claimFlags: ClaimFlag[] = [
      {
        claim_id: 'sec1.c1',
        section_id: 'sec1',
        verdict: 'partially_supported',
        rationale: 'Only one independent source backs this figure.',
        supporting_source_ids: ['s1'],
      },
    ]

    renderRenderer('Funding rose <span data-claim="sec1.c1">18%</span>.', claimFlags)

    await user.hover(screen.getByText('18%'))

    await waitFor(() => {
      expect(screen.getByText('Only one independent source backs this figure.')).toBeVisible()
      expect(screen.getByText('partially supported')).toBeVisible()
    })
  })

  it('normalizes caret-less citation markers into interactive footnotes', async () => {
    const user = userEvent.setup()
    renderRenderer('See the data[s1].')

    const footnote = screen.getByRole('link', { name: '[1]' })
    expect(footnote).toHaveAttribute('href', '#s1')

    await user.hover(footnote)

    await waitFor(() => {
      expect(screen.getByText('Dealroom Q1 2026')).toBeVisible()
      expect(screen.getByText('dealroom.co')).toBeVisible()
      expect(screen.getByText('Cred .92')).toBeVisible()
    })
  })

  it('renders GFM pipe tables as HTML tables', () => {
    const { container } = renderRenderer(
      '| Region | Deals |\n| --- | ---: |\n| CEE | 412 |\n| DACH | 891 |',
      [],
      [],
    )

    const table = container.querySelector('table')
    expect(table).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Region' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '412' })).toBeInTheDocument()
  })

  it('strips script tags from markdown while keeping safe text', () => {
    const { container } = renderRenderer('<script>alert("xss")</script>Safe paragraph.', [], [])

    expect(container.querySelector('script')).not.toBeInTheDocument()
    expect(screen.getByText('Safe paragraph.')).toBeInTheDocument()
  })

  it('calls onSourceClick instead of scrolling when a footnote is activated', async () => {
    const user = userEvent.setup()
    const onSourceClick = vi.fn()
    const section: ReportSection = {
      id: 'sec1',
      heading: 'Section',
      body_md: 'Cited here.[^s1]',
      cited_source_ids: ['s1'],
    }

    render(
      <TooltipProvider>
        <ReportRenderer
          section={section}
          claimFlags={[]}
          sources={sources}
          onSourceClick={onSourceClick}
        />
      </TooltipProvider>,
    )

    await user.click(screen.getByRole('link', { name: '[1]' }))
    expect(onSourceClick).toHaveBeenCalledWith('s1')
  })
})
