import { useEffect, useState, type CSSProperties } from 'react'

import { ArrowRight } from 'lucide-react'

import { CONSTELLATION_AGENTS, THIS_WEEK } from './landing-content'

const LOOP_SECONDS = 18
const DASH_LEN = 640

export function AgentConstellation() {
  const [t, setT] = useState(0)

  useEffect(() => {
    let raf = 0
    let start: number | null = null
    const tick = (now: number) => {
      if (start === null) start = now
      setT(((now - start) / 1000) % LOOP_SECONDS)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  const lineIdx = Math.floor((t / LOOP_SECONDS) * THIS_WEEK.length) % THIS_WEEK.length
  const traceOffset = DASH_LEN - (((t / LOOP_SECONDS) * DASH_LEN * 2) % (DASH_LEN * 2))

  return (
    <aside className="flex flex-col gap-5 lg:gap-6 lg:border-l lg:border-line lg:pl-8">
      <div className="flex items-center justify-between">
        <span className="micro">A research desk, in three hands</span>
        <span className="micro text-muted">fig. 01</span>
      </div>

      <div className="relative border border-line bg-bg-2">
        <div className="relative h-[340px] overflow-hidden sm:h-[400px]">
          <svg
            aria-hidden
            className="absolute inset-0"
            width="100%"
            height="100%"
            viewBox="0 0 440 320"
            preserveAspectRatio="xMidYMid slice"
            style={{ opacity: 0.5 }}
          >
            <defs>
              <pattern id="ac-grid" width="22" height="22" patternUnits="userSpaceOnUse">
                <path
                  d="M 22 0 L 0 0 0 22"
                  fill="none"
                  stroke="var(--line-soft)"
                  strokeWidth="0.5"
                />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#ac-grid)" />
          </svg>

          <svg
            aria-hidden
            className="absolute inset-0"
            width="100%"
            height="100%"
            viewBox="0 0 440 320"
            preserveAspectRatio="xMidYMid meet"
          >
            <polygon
              points={CONSTELLATION_AGENTS.map((a) => `${a.pos.x},${a.pos.y}`).join(' ')}
              fill="none"
              stroke="var(--line)"
              strokeWidth="0.75"
              strokeDasharray="2 4"
              opacity="0.7"
            />

            <polygon
              points={CONSTELLATION_AGENTS.map((a) => `${a.pos.x},${a.pos.y}`).join(' ')}
              fill="none"
              stroke="var(--fg)"
              strokeWidth="1"
              strokeLinecap="round"
              strokeDasharray="50 590"
              strokeDashoffset={traceOffset}
              opacity="0.5"
            />

            {CONSTELLATION_AGENTS.map((a) => (
              <g key={a.key} transform={`translate(${a.pos.x}, ${a.pos.y})`}>
                <circle r="22" fill={`var(--${a.key}-soft)`} />
                <circle r="14" fill={`var(--${a.key})`} />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontFamily="var(--serif)"
                  fontSize="14"
                  fontStyle="italic"
                  fill={a.key === 'scribe' ? 'var(--ink)' : 'var(--bg)'}
                >
                  {a.name[0]}
                </text>
              </g>
            ))}

            {CONSTELLATION_AGENTS.map((a) => {
              const isScout = a.key === 'scout'
              const isScribe = a.key === 'scribe'
              const isCritic = a.key === 'critic'
              const lx = isScout ? a.pos.x + 20 : isScribe ? a.pos.x - 20 : a.pos.x
              const ly = isCritic ? a.pos.y + 42 : a.pos.y - 6
              const anchor: 'start' | 'end' | 'middle' = isScout
                ? 'start'
                : isScribe
                  ? 'end'
                  : 'middle'
              return (
                <g key={`l-${a.key}`} transform={`translate(${lx}, ${ly})`}>
                  <text
                    textAnchor={anchor}
                    fontFamily="var(--serif)"
                    fontSize="26"
                    fontWeight="400"
                    fill="var(--fg)"
                    style={{ letterSpacing: '-0.02em' }}
                  >
                    {a.name}
                  </text>
                  <text
                    textAnchor={anchor}
                    y="22"
                    fontFamily="var(--mono)"
                    fontSize="13"
                    letterSpacing="0.08em"
                    fill="var(--muted)"
                    style={{ textTransform: 'uppercase' }}
                  >
                    {a.role}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        <div className="border-t border-line bg-bg px-4 py-4 sm:px-[18px]">
          <div className="micro mb-2 text-muted">This week, on the desk</div>
          <div className="relative min-h-[44px]">
            {THIS_WEEK.map((q, i) => {
              const active = i === lineIdx
              const style: CSSProperties = {
                position: 'absolute',
                inset: 0,
                opacity: active ? 1 : 0,
                transform: active ? 'translateY(0)' : 'translateY(4px)',
                transition: 'opacity 600ms ease, transform 600ms ease',
              }
              return (
                <div
                  key={q}
                  className="serif text-base font-light italic leading-snug text-fg sm:text-[17px]"
                  style={style}
                >
                  “{q}”
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="flex items-start gap-3.5">
        <div className="w-px self-stretch bg-line" />
        <div className="serif text-[13px] font-light italic leading-relaxed text-fg-2">
          A question travels Scout <ArrowRight className="inline-block size-3 align-middle" />{' '}
          Scribe <ArrowRight className="inline-block size-3 align-middle" /> Critic, and comes back
          as a report you can defend.
        </div>
      </div>
    </aside>
  )
}
