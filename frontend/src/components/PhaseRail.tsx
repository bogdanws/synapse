import { AGENTS } from './ui/Agent'
import { cn } from './ui/cn'
import type { CurrentPhase } from '../hooks/useDerivedJobState'

interface PhaseRailProps {
  currentPhase: CurrentPhase
  /** Whether Scout finished its handoff before the current state was reached. Used to render accurate progress on `failed`. */
  scoutComplete: boolean
  /** Whether Scribe finished its handoff before the current state was reached. Used to render accurate progress on `failed`. */
  scribeComplete: boolean
  /** Shown when the job has just completed — brief flash before navigation. */
  completionMessage?: string
}

interface PhaseStop {
  key: 'scout' | 'scribe' | 'critic'
  stageLabel: string
  role: string
  doneVerb: string
  activeVerb: string
  queueVerb: string
}

const STOPS: PhaseStop[] = [
  {
    key: 'scout',
    stageLabel: 'Stage 1',
    role: 'gathers evidence',
    doneVerb: 'Gathered',
    activeVerb: 'Gathering now',
    queueVerb: 'Awaiting',
  },
  {
    key: 'scribe',
    stageLabel: 'Stage 2',
    role: 'writes the report',
    doneVerb: 'Drafted',
    activeVerb: 'Drafting now',
    queueVerb: 'Awaiting draft',
  },
  {
    key: 'critic',
    stageLabel: 'Stage 3',
    role: 'verifies every claim',
    doneVerb: 'Verified',
    activeVerb: 'Verifying now',
    queueVerb: 'Awaiting draft',
  },
]

function stopStatus(
  key: 'scout' | 'scribe' | 'critic',
  currentPhase: CurrentPhase,
  scoutComplete: boolean,
  scribeComplete: boolean,
): 'done' | 'active' | 'queue' {
  const order: Array<'scout' | 'scribe' | 'critic'> = ['scout', 'scribe', 'critic']
  const idx = order.indexOf(key)
  if (currentPhase === 'done') {
    return 'done'
  }
  if (currentPhase === 'failed') {
    // We don't know which phase raised the error from `currentPhase` alone, so
    // derive it from the completion flags: the first phase that hadn't handed
    // off is the one that broke. Phases before it ran to completion; phases
    // after it never started.
    const failedIdx = !scoutComplete ? 0 : !scribeComplete ? 1 : 2
    if (idx < failedIdx) return 'done'
    if (idx === failedIdx) return 'active'
    return 'queue'
  }
  const currentIdx = order.indexOf(currentPhase as 'scout' | 'scribe' | 'critic')
  if (idx < currentIdx) return 'done'
  if (idx === currentIdx) return 'active'
  return 'queue'
}

export function PhaseRail({
  currentPhase,
  scoutComplete,
  scribeComplete,
  completionMessage,
}: PhaseRailProps) {
  return (
    <div
      className="border-b border-line px-8 py-5"
      style={{ background: 'var(--bg-2)' }}
      aria-label="pipeline progress"
    >
      <div className="micro mb-3">Pipeline · agents run in sequence</div>

      {completionMessage && (
        <div
          className="mb-3 text-center label"
          style={{ color: 'var(--scribe)' }}
          role="status"
          aria-live="polite"
        >
          {completionMessage}
        </div>
      )}

      <div className="grid grid-cols-3 relative">
        {/* Connector spine behind the discs */}
        <div
          className="absolute h-px top-[13px]"
          style={{
            left: '16%',
            right: '16%',
            background: 'var(--line)',
          }}
          aria-hidden
        />

        {STOPS.map((stop) => {
          const status = stopStatus(stop.key, currentPhase, scoutComplete, scribeComplete)
          const meta = AGENTS[stop.key]
          const isDone = status === 'done'
          const isActive = status === 'active'
          const isQueue = status === 'queue'

          return (
            <div
              key={stop.key}
              className={cn('flex flex-col items-center relative', isQueue && 'opacity-55')}
            >
              {/* Identity disc */}
              <div
                className="w-[26px] h-[26px] rounded-full flex items-center justify-center relative z-10"
                style={{
                  background: isDone ? `var(--${stop.key})` : 'var(--bg)',
                  border: `2px solid ${isDone || isActive ? `var(--${stop.key})` : 'var(--line)'}`,
                  color: isDone ? 'white' : `var(--${stop.key})`,
                  fontFamily: 'var(--serif)',
                  fontSize: 13,
                  fontWeight: 500,
                  // Scribe needs ink text for contrast on its amber background.
                  ...(isDone && stop.key === 'scribe' ? { color: 'var(--ink)' } : {}),
                }}
                aria-hidden
              >
                {isDone ? '✓' : meta.initial}
              </div>

              <div className="mt-3 text-center">
                <div
                  className="serif text-[18px] font-medium"
                  style={{ letterSpacing: '-0.015em' }}
                >
                  {meta.name}
                  {isActive && (
                    <span
                      className="pulse-dot inline-block ml-2"
                      style={{ color: `var(--${stop.key})` }}
                      aria-hidden
                    />
                  )}
                </div>
                <div className="micro mt-1">
                  {stop.stageLabel} · {stop.role}
                </div>
                <div
                  className="label mt-2"
                  style={{
                    color: isActive
                      ? `var(--${stop.key})`
                      : isDone
                        ? 'var(--muted)'
                        : 'var(--muted)',
                  }}
                >
                  {isDone ? stop.doneVerb : isActive ? stop.activeVerb : stop.queueVerb}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
