import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SourceRow } from './SourceRow'
import type { Source } from '../types/api'

const mockSource: Source = {
  id: 's1',
  url: 'https://example.com/article',
  title: 'Example Article',
  credibility: 0.85,
  relevance: 0.92,
  snippet: 'A snippet.',
}

describe('SourceRow', () => {
  it('renders with id and class for footnote targeting', () => {
    render(<SourceRow source={mockSource} index={0} />)

    const row = document.getElementById('s1')
    expect(row).toBeInTheDocument()
    expect(row).toHaveClass('source-row')
  })

  it('links to the full URL', () => {
    render(<SourceRow source={mockSource} index={0} />)

    const link = screen.getByText((content) => content.includes(mockSource.title)).closest('a')
    expect(link).toHaveAttribute('href', mockSource.url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noreferrer')
  })

  it('renders favicon via Google S2', () => {
    const { container } = render(<SourceRow source={mockSource} index={0} />)

    const img = container.querySelector('img[src*="google.com/s2/favicons"]')
    expect(img).toBeInTheDocument()
    expect(img).toHaveAttribute('width', '16')
    expect(img).toHaveAttribute('height', '16')
  })

  it('renders domain, credibility and relevance', () => {
    render(<SourceRow source={mockSource} index={0} />)

    expect(screen.getByText('example.com')).toBeInTheDocument()
    expect(screen.getByText('Cred')).toBeInTheDocument()
    expect(screen.getByText('Rel')).toBeInTheDocument()
  })

  it('sets data-highlighted="true" when highlighted', () => {
    render(<SourceRow source={mockSource} index={0} highlighted />)

    const row = document.getElementById('s1')
    expect(row).toHaveAttribute('data-highlighted', 'true')
  })

  it('sets data-highlighted="false" when not highlighted', () => {
    render(<SourceRow source={mockSource} index={0} highlighted={false} />)

    const row = document.getElementById('s1')
    expect(row).toHaveAttribute('data-highlighted', 'false')
  })

  it('defaults data-highlighted to false', () => {
    render(<SourceRow source={mockSource} index={0} />)

    const row = document.getElementById('s1')
    expect(row).toHaveAttribute('data-highlighted', 'false')
  })
})
