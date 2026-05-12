import type { ReactNode, MouseEvent } from 'react'

import { cn } from './ui/cn'
import { AgentDot } from './ui/AgentDot'
import type { Agent } from './ui/Agent'

interface PillProps {
  label: string
  value: ReactNode
  agent?: Agent
  interactive?: boolean
  disabled?: boolean
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void
  className?: string
}

/*
 * Compact metadata pill from the figma: micro label above, sans value below,
 * optional leading agent dot. Interactive variant lifts on hover; disabled
 * reduces opacity and blocks pointer events.
 */
export function Pill({
  label,
  value,
  agent,
  interactive,
  disabled,
  onClick,
  className,
}: PillProps) {
  const content = (
    <>
      {agent && <AgentDot agent={agent} size={18} className="mr-1" />}
      <div className="flex flex-col items-start">
        <span className="micro leading-none">{label}</span>
        <div className="font-sans text-[12px] leading-tight mt-0.5">{value}</div>
      </div>
    </>
  )

  const baseClasses = cn(
    'inline-flex items-center gap-1.5 border border-line px-3 py-1.5 transition-colors duration-150',
    interactive &&
      !disabled &&
      'cursor-pointer hover:-translate-y-px transition-transform duration-100',
    // When a focusable child (e.g. Select trigger) is hovered or focused, brighten the pill border
    // so the whole pill feels active, without making the pill itself a button.
    !disabled &&
      'has-[button:hover]:border-fg has-[button:focus-visible]:border-fg has-[[data-popup-open]]:border-fg',
    disabled && 'opacity-50 cursor-not-allowed',
    className,
  )

  if (interactive || onClick) {
    return (
      <button type="button" onClick={onClick} disabled={disabled} className={baseClasses}>
        {content}
      </button>
    )
  }

  return <div className={baseClasses}>{content}</div>
}
