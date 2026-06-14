import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ContradictionsList } from './ContradictionsList'
import type { Contradiction, Source } from '../types/api'

const sources: Source[] = [
  {
    id: 's1',
    url: 'https://dealroom.co',
    title: 'Dealroom',
    credibility: 0.92,
    relevance: 0.88,
    snippet: '',
  },
  {
    id: 's2',
    url: 'https://pitchbook.com',
    title: 'PitchBook',
    credibility: 0.75,
    relevance: 0.6,
    snippet: '',
  },
]

const contradictions: Contradiction[] = [
  {
    topic: 'Direction of deal volume',
    positions: [
      { statement: 'Deal volume is growing.', source_ids: ['s1'] },
      { statement: 'Deal volume is declining.', source_ids: ['s2'] },
    ],
  },
]

describe('ContradictionsList', () => {
  it('renders the topic as a heading', () => {
    render(
      <ContradictionsList
        contradictions={contradictions}
        sources={sources}
        onSourceClick={vi.fn()}
      />,
    )
    expect(screen.getByRole('heading', { name: /Direction of deal volume/i })).toBeInTheDocument()
  })

  it('renders each position statement', () => {
    render(
      <ContradictionsList
        contradictions={contradictions}
        sources={sources}
        onSourceClick={vi.fn()}
      />,
    )
    expect(screen.getByText('Deal volume is growing.')).toBeInTheDocument()
    expect(screen.getByText('Deal volume is declining.')).toBeInTheDocument()
  })

  it('attributes each statement to its own source pill', () => {
    render(
      <ContradictionsList
        contradictions={contradictions}
        sources={sources}
        onSourceClick={vi.fn()}
      />,
    )
    // s1 -> ordinal [1] Dealroom under the "growing" side; s2 -> [2] PitchBook
    // under the "declining" side. The ordinals match the References list.
    expect(screen.getByRole('button', { name: /\[1\] Dealroom/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /\[2\] PitchBook/ })).toBeInTheDocument()
  })

  it('calls onSourceClick with the source id when a pill is clicked', () => {
    const onSourceClick = vi.fn()
    render(
      <ContradictionsList
        contradictions={contradictions}
        sources={sources}
        onSourceClick={onSourceClick}
      />,
    )
    screen.getByRole('button', { name: /Dealroom/ }).click()
    expect(onSourceClick).toHaveBeenCalledWith('s1')
  })

  it('renders one "vs" divider between two opposing positions', () => {
    render(
      <ContradictionsList
        contradictions={contradictions}
        sources={sources}
        onSourceClick={vi.fn()}
      />,
    )
    expect(screen.getAllByText('vs')).toHaveLength(1)
  })

  it('degrades gracefully when a source id is unknown', () => {
    render(
      <ContradictionsList
        contradictions={[
          {
            topic: 'Mystery',
            positions: [
              { statement: 'Known side.', source_ids: ['s1'] },
              { statement: 'Unknown side.', source_ids: ['ghost'] },
            ],
          },
        ]}
        sources={sources}
        onSourceClick={vi.fn()}
      />,
    )
    // The unknown id renders as plain text rather than a clickable pill.
    expect(screen.getByText('ghost')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ghost/ })).not.toBeInTheDocument()
  })
})
