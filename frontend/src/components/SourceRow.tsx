import type { Source } from '../types/api'
import { credibilityColor, extractDomain } from '../lib/source-utils'
import { cn } from './ui/cn'

interface ScoreBarProps {
  label: string
  score: number
}

function ScoreBar({ label, score }: ScoreBarProps) {
  const color = credibilityColor(score)
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)))

  return (
    <div
      role="meter"
      aria-label={`${label}: ${pct}%`}
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      className="flex items-center gap-1"
    >
      <span className="font-mono text-xs uppercase tracking-widest text-muted">{label}</span>
      <div className="h-0.5 w-8 bg-line">
        <div className="h-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono text-xs" style={{ color }}>
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
      className={cn('source-row pb-3')}
      data-highlighted={highlighted ? 'true' : 'false'}
      style={{ breakInside: 'avoid' }}
    >
      <div className="flex items-center gap-2">
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
          <div className="mt-1 flex flex-wrap items-center gap-2.5">
            <span className="font-mono text-xs uppercase tracking-widest text-muted">
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
