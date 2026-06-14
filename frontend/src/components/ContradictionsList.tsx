import { Fragment } from 'react'

import type { Contradiction, ContradictionPosition, Source } from '../types/api'
import { credibilityColor } from '../lib/source-utils'

interface ContradictionsListProps {
  contradictions: Contradiction[]
  sources: Source[]
  onSourceClick: (id: string) => void
}

interface SourceEntry {
  source: Source
  ordinal: number
}

export function ContradictionsList({
  contradictions,
  sources,
  onSourceClick,
}: ContradictionsListProps) {
  // Index short source id -> {source, ordinal} so each pill can show its
  // reference number and credibility dot without an O(n) scan per render. The
  // ordinal matches the 1-based index in the References section.
  const sourceIndex = new Map<string, SourceEntry>(
    sources.map((src, i) => [src.id, { source: src, ordinal: i + 1 }]),
  )

  return (
    <ol
      style={{
        listStyle: 'none',
        padding: 0,
        margin: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 28,
      }}
    >
      {contradictions.map((contradiction, i) => (
        <li
          key={i}
          style={{
            paddingLeft: 16,
            borderLeft: '2px solid var(--critic)',
          }}
        >
          {/* The disputed dimension — names *what* the sources disagree on, so
              the opposing statements below have a shared frame of reference. */}
          <h3
            className="serif"
            style={{
              margin: '0 0 14px 0',
              fontSize: 15,
              lineHeight: 1.4,
              fontWeight: 500,
              color: 'var(--fg)',
            }}
          >
            {contradiction.topic}
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {contradiction.positions.map((position, j) => (
              <Fragment key={j}>
                {j > 0 && <VersusDivider />}
                <Position
                  position={position}
                  sourceIndex={sourceIndex}
                  onSourceClick={onSourceClick}
                />
              </Fragment>
            ))}
          </div>
        </li>
      ))}
    </ol>
  )
}

function VersusDivider() {
  return (
    <div className="flex items-center gap-3" style={{ margin: '10px 0' }} aria-hidden>
      <span className="flex-1" style={{ height: 1, background: 'var(--line-soft)' }} />
      <span className="micro" style={{ color: 'var(--critic)' }}>
        vs
      </span>
      <span className="flex-1" style={{ height: 1, background: 'var(--line-soft)' }} />
    </div>
  )
}

interface PositionProps {
  position: ContradictionPosition
  sourceIndex: Map<string, SourceEntry>
  onSourceClick: (id: string) => void
}

function Position({ position, sourceIndex, onSourceClick }: PositionProps) {
  return (
    <div
      className="flex flex-col gap-2.5 border border-line-soft p-3"
      style={{ background: 'var(--bg-2)' }}
    >
      <p
        className="serif"
        style={{
          margin: 0,
          fontSize: 14,
          lineHeight: 1.55,
          fontWeight: 300,
          color: 'var(--fg)',
        }}
      >
        {position.statement}
      </p>
      <div className="flex flex-wrap gap-2">
        {position.source_ids.map((id) => {
          const entry = sourceIndex.get(id)
          if (!entry) {
            // Shouldn't occur post-validation, but degrade gracefully.
            return (
              <span key={id} className="font-mono text-xs" style={{ color: 'var(--muted)' }}>
                {id}
              </span>
            )
          }
          return <SourcePill key={id} entry={entry} onClick={() => onSourceClick(id)} />
        })}
      </div>
    </div>
  )
}

function SourcePill({ entry, onClick }: { entry: SourceEntry; onClick: () => void }) {
  const { source, ordinal } = entry
  const color = credibilityColor(source.credibility)
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 border border-line-soft bg-bg px-2 py-1"
      style={{ cursor: 'pointer', font: 'inherit', textAlign: 'left' }}
    >
      <span className="size-1 rounded-full shrink-0" style={{ background: color }} aria-hidden />
      <span className="font-sans text-xs" style={{ color: 'var(--fg-2)' }}>
        [{ordinal}] {source.title}
      </span>
      <span className="font-mono text-xs" style={{ color }}>
        .{Math.round(source.credibility * 100)}
      </span>
    </button>
  )
}
