import type { Source } from '../types/api'
import { credibilityColor, extractDomain } from '../lib/source-utils'

interface ScoreBarProps {
  label: string
  score: number
}

function ScoreBar({ label, score }: ScoreBarProps) {
  const color = credibilityColor(score)
  const pct = Math.round(score * 100)

  return (
    <div
      role="meter"
      aria-label={`${label}: ${pct}%`}
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{ display: 'flex', alignItems: 'center', gap: 4 }}
    >
      <span
        className="font-mono"
        style={{
          fontSize: 9,
          color: 'var(--muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        {label}
      </span>
      <div style={{ width: 32, height: 2, background: 'var(--line)' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color }} />
      </div>
      <span className="font-mono" style={{ fontSize: 9, color }}>
        .{pct}
      </span>
    </div>
  )
}

interface SourceRowProps {
  source: Source
  index: number
  highlighted?: boolean
}

export function SourceRow({ source, index, highlighted }: SourceRowProps) {
  return (
    <li
      id={source.id}
      className="source-row"
      data-highlighted={highlighted ? 'true' : 'false'}
      style={{ paddingBottom: 12, breakInside: 'avoid' }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <img
          src={`https://www.google.com/s2/favicons?domain=${extractDomain(source.url)}&sz=32`}
          alt=""
          width={16}
          height={16}
          style={{ flexShrink: 0 }}
          onError={(e) => {
            ;(e.target as HTMLImageElement).style.display = 'none'
          }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <a
            href={source.url}
            target="_blank"
            rel="noreferrer"
            style={{ color: 'inherit', textDecoration: 'none' }}
          >
            [{index + 1}] {source.title}
          </a>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginTop: 4,
              flexWrap: 'wrap',
            }}
          >
            <span
              className="font-mono"
              style={{
                fontSize: 9,
                color: 'var(--muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              {extractDomain(source.url)}
            </span>
            <ScoreBar label="Cred" score={source.credibility} />
            <ScoreBar label="Rel" score={source.relevance} />
          </div>
        </div>
      </div>
    </li>
  )
}
