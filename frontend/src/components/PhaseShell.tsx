import type { ReactNode } from 'react'

import type { Agent } from './ui/Agent'
import { AgentDot } from './ui/AgentDot'
import { cn } from './ui/cn'

interface PhaseShellProps {
  agent: Agent
  stageNum: string
  title: string
  summary: string
  status: 'done' | 'active' | 'queue'
  defaultOpen?: boolean
  children?: ReactNode
}

/*
 * Collapsible phase card wrapper. The left 3px border and soft background
 * when active are the primary editorial signals for which phase is live;
 * the queue state dims the entire card so focus stays on the active phase.
 */
export function PhaseShell({
  agent,
  stageNum,
  title,
  summary,
  status,
  defaultOpen,
  children,
}: PhaseShellProps) {
  const isActive = status === 'active'
  const isDone = status === 'done'
  const isQueue = status === 'queue'

  const open = defaultOpen ?? status !== 'queue'

  const borderColor = isActive || isDone ? `var(--${agent})` : 'var(--line)'
  const bgColor = isActive ? `var(--${agent}-soft)` : 'var(--bg)'

  return (
    <section
      className={cn('mb-4 border border-line p-5 px-6', isQueue && 'opacity-[0.78]')}
      style={{
        borderLeft: `3px solid ${borderColor}`,
        background: bgColor,
      }}
      aria-label={`${agent} phase`}
    >
      <div className="flex items-center gap-4">
        <div className="relative">
          <AgentDot agent={agent} size={32} halo={isActive} />
          <span
            className="font-mono absolute -bottom-1 -right-1 text-xs leading-none"
            style={{ color: `var(--${agent})` }}
            aria-hidden
          >
            {stageNum}
          </span>
        </div>
        <div className="flex-1">
          <div className="serif text-xl font-normal tracking-tight leading-tight">{title}</div>
          <div className="micro mt-1.5">{summary}</div>
        </div>
        <div
          className="flex items-center gap-2 label"
          style={{
            color: isActive ? `var(--${agent})` : 'var(--muted)',
          }}
        >
          {isActive && <span className="pulse-dot" aria-hidden />}
          <span>{isDone ? 'Complete' : isActive ? 'Running now' : 'Up next'}</span>
        </div>
      </div>

      {open && children && <div>{children}</div>}
    </section>
  )
}
