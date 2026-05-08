import type { CSSProperties } from 'react'

import { AGENTS, type Agent } from './Agent'
import { cn } from './cn'

interface AgentDotProps {
  agent: Agent
  /** Pixel size of the disc. Default 26 matches the editorial baseline. */
  size?: number
  className?: string
  /** Soft halo behind the disc — used when the agent is currently running. */
  halo?: boolean
}

/*
 * Identity disc for an agent. Background and label colour come from the
 * `.agent-dot.<key>` rules in index.css so dark-mode adjustments live in one
 * place. The serif initial inside is a deliberate editorial flourish — it
 * reads like a bookplate stamp rather than a SaaS avatar.
 */
export function AgentDot({ agent, size = 26, halo, className }: AgentDotProps) {
  const meta = AGENTS[agent]
  const style: CSSProperties = {
    width: size,
    height: size,
    fontSize: Math.round(size * 0.5),
  }
  if (halo) {
    style.boxShadow = `0 0 0 ${Math.max(2, Math.round(size * 0.12))}px var(--${agent}-soft)`
  }
  return (
    <span className={cn('agent-dot', agent, className)} style={style} aria-label={meta.name}>
      {meta.initial}
    </span>
  )
}
