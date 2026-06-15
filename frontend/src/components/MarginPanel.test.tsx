import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

import { MarginPanel } from './MarginPanel'
import type { ClaimFlag } from '../types/api'

function mockDesktopViewport() {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
}

const supportedFlag: ClaimFlag = {
  claim_id: 'sec1.c1',
  section_id: 'sec1',
  verdict: 'supported',
  rationale: 'Verified against primary data.',
  supporting_source_ids: ['s1'],
}

describe('MarginPanel', () => {
  beforeEach(() => {
    mockDesktopViewport()
  })

  it('renders VERIFIED badge with scout-coloured border for supported claims', () => {
    render(<MarginPanel claimFlags={[supportedFlag]} />)

    expect(screen.getByText('VERIFIED')).toBeInTheDocument()
    expect(screen.getByText('Verified against primary data.')).toBeInTheDocument()

    const annotation = screen.getByText('VERIFIED').closest('div.border-l-2')
    expect(annotation?.getAttribute('style')).toContain('var(--scout)')
  })

  it('maps each verdict to its margin badge label', () => {
    const flags: ClaimFlag[] = [
      { ...supportedFlag, claim_id: 'c1', verdict: 'supported' },
      {
        ...supportedFlag,
        claim_id: 'c2',
        verdict: 'partially_supported',
        rationale: 'Weak corroboration.',
      },
      {
        ...supportedFlag,
        claim_id: 'c3',
        verdict: 'unsupported',
        rationale: 'No corroborating source.',
      },
      {
        ...supportedFlag,
        claim_id: 'c4',
        verdict: 'contradicted',
        rationale: 'Directly contradicted.',
      },
    ]

    render(<MarginPanel claimFlags={flags} />)

    expect(screen.getByText('VERIFIED')).toBeInTheDocument()
    expect(screen.getByText('PARTIAL')).toBeInTheDocument()
    expect(screen.getByText('UNSUPPORTED')).toBeInTheDocument()
    expect(screen.getByText('CONTRADICTED')).toBeInTheDocument()
  })

  it('renders section confidence via ConfidenceBar when a score is provided', () => {
    render(<MarginPanel claimFlags={[supportedFlag]} confidence={0.94} />)

    expect(screen.getByText('Confidence')).toBeInTheDocument()
    expect(screen.getByText('.94')).toBeInTheDocument()
  })
})
