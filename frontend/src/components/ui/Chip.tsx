import type { HTMLAttributes, ReactNode } from 'react'

import type { Agent } from './Agent'
import { cn } from './cn'

interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  /** Tints the chip with the agent's colour and border. */
  agent?: Agent
  /** Renders a small leading dot in `currentColor`. */
  dot?: boolean
  children: ReactNode
}

/*
 * Pill chip for status labels and metadata. Reuses the global `.chip`
 * declaration from index.css so styling stays consistent with the figma's
 * loose-leaf inline labels.
 */
export function Chip({ agent, dot, className, children, ...props }: ChipProps) {
  return (
    <span className={cn('chip', agent, className)} {...props}>
      {dot && <span className="dot" />}
      {children}
    </span>
  )
}
