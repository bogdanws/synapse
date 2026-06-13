import { cn } from './ui/cn'

interface ConfidenceBarProps {
  value: number
  className?: string
}

/*
 * 1px-tall confidence track from the figma. Colour maps to the agent that
 * would have produced the score: scout for high confidence, scribe for medium,
 * critic for low. The mono decimal label (.{pct}) is fixed-width so the bar
 * width stays stable as numbers change.
 */
export function ConfidenceBar({ value, className }: ConfidenceBarProps) {
  const pct = Math.round(value * 100)
  const color = value > 0.85 ? 'bg-scout' : value > 0.75 ? 'bg-scribe' : 'bg-critic'

  return (
    <div className={cn('flex items-center gap-2 flex-1', className)}>
      <div className="flex-1 h-[2px] bg-line relative">
        <div className={cn('absolute left-0 top-0 bottom-0', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs text-muted w-7 text-right">.{pct}</span>
    </div>
  )
}
