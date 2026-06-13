import { credibilityColor } from '../lib/source-utils'

interface SourcePillProps {
  title: string
  credibility: number | null
}

export function SourcePill({ title, credibility }: SourcePillProps) {
  const color = credibility !== null ? credibilityColor(credibility) : 'var(--muted)'

  return (
    <div className="inline-flex items-center gap-1.5 border border-line-soft bg-bg px-2 py-1">
      <span className="size-1 rounded-full shrink-0" style={{ background: color }} aria-hidden />
      <span className="font-sans text-xs" style={{ color: 'var(--fg-2)' }}>
        {title}
      </span>
      {credibility !== null ? (
        <span className="font-mono text-xs" style={{ color }}>
          .{Math.round(credibility * 100)}
        </span>
      ) : (
        // Loading pulse shown while the source_scored event for this source hasn't arrived yet.
        <span
          className="pulse-dot"
          style={{ color: 'var(--muted)' }}
          aria-label="loading credibility score"
        />
      )}
    </div>
  )
}
