import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'

import { useFontsReady } from '../../hooks/useFontsReady'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

import { PIPELINE_RUNS, type AgentKey, type DraftToken } from './landing-content'

/*
 * AgentPipelineHero — a scripted, looping visualisation of one research
 * cycle. The single source of motion is the page-level clock `t` (seconds
 * elapsed in the current loop), pushed every animation frame. Every reveal
 * (sources, draft tokens, redline underline, confidence bar) is derived
 * from `t` against phase boundaries, so the demo is fully deterministic
 * and the wrap is clean.
 *
 * Total loop is intentionally long enough to read — viewers should be
 * able to skim the query, watch four sources land, see the draft form,
 * read the Critic's redline, and still have a moment to register the
 * confidence score before the next query takes over.
 */

const LOOP_SECONDS = 26

const PHASES = {
  query: [0, 1.4],
  scout: [1.4, 8.0],
  scribe: [8.0, 16.5],
  critic: [16.5, 24.5],
  rest: [24.5, 26.0],
} as const

function progressIn(t: number, span: readonly [number, number]): number {
  if (t <= span[0]) return 0
  if (t >= span[1]) return 1
  return (t - span[0]) / (span[1] - span[0])
}

export function AgentPipelineHero() {
  const reduced = usePrefersReducedMotion()
  const fontsReady = useFontsReady()
  // When motion is reduced we freeze at the "rest" phase of the first run:
  // everything fully revealed, no loop, no animation.
  const [t, setT] = useState(0)
  const [runIdx, setRunIdx] = useState(0)

  useEffect(() => {
    if (reduced || !fontsReady) return
    let raf = 0
    let start: number | null = null
    let lastCycle = 0
    const tick = (now: number) => {
      if (start === null) start = now
      const elapsed = (now - start) / 1000
      const cycle = Math.floor(elapsed / LOOP_SECONDS) % PIPELINE_RUNS.length
      if (cycle !== lastCycle) {
        lastCycle = cycle
        setRunIdx(cycle)
      }
      setT(elapsed % LOOP_SECONDS)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [reduced, fontsReady])

  const run = PIPELINE_RUNS[runIdx]

  // How many sources / draft tokens have been revealed so far. The `+ 0.2`
  // and `+ 0.5` nudges make the last item land slightly before the phase
  // formally ends, leaving a beat for the eye to settle.
  const sourcesShown = reduced
    ? run.sources.length
    : Math.min(
        run.sources.length,
        Math.floor(progressIn(t, PHASES.scout) * (run.sources.length + 0.2)),
      )

  const tokensShown = reduced
    ? run.draft.length
    : Math.min(
        run.draft.length,
        Math.floor(progressIn(t, PHASES.scribe) * (run.draft.length + 0.5)),
      )

  // Critic phase: three discrete events fire in sequence — the redline
  // gets slashed, the margin note appears, the confidence stamp lands.
  // These are booleans, not continuous progress, so each animation runs
  // at a snappy fixed duration via CSS transitions rather than reading
  // like a loading bar.
  const criticT = t - PHASES.critic[0]
  const underlineFired = reduced || criticT > 0.4
  const criticNoteVisible = reduced || criticT > 1.0
  const confidenceFired = reduced || criticT > 1.6

  // Soft tint on whichever block is currently working.
  const activeAgent: AgentKey | null =
    t < PHASES.query[1]
      ? null
      : t < PHASES.scout[1]
        ? 'scout'
        : t < PHASES.scribe[1]
          ? 'scribe'
          : t < PHASES.critic[1]
            ? 'critic'
            : null

  // Fade the whole panel at the loop seam so the reset never snaps.
  const pageAlpha = reduced
    ? 1
    : Math.min(Math.min(1, t / 0.35), t > LOOP_SECONDS - 0.9 ? (LOOP_SECONDS - t) / 0.9 : 1)

  return (
    <aside
      className="flex flex-col gap-5 lg:gap-6 lg:border-l lg:border-line lg:pl-8"
      style={{ opacity: pageAlpha }}
    >
      {/* The key remounts the inner subtree at each run boundary so stale
          opacity transitions can't bleed across queries. */}
      <div key={runIdx} className="border border-line bg-bg-2">
        <QueryRow query={run.query} progress={progressIn(t, PHASES.query)} reduced={reduced} />

        <Block agent="scout" label="Scout" sub="researches" active={activeAgent === 'scout'}>
          <div className="mt-3 space-y-1.5">
            {run.sources.map((source, i) => (
              <SourceLine
                key={i}
                num={i + 1}
                title={source.title}
                credibility={source.credibility}
                visible={i < sourcesShown}
                reduced={reduced}
              />
            ))}
          </div>
        </Block>

        <Block agent="scribe" label="Scribe" sub="synthesises" active={activeAgent === 'scribe'}>
          <DraftView
            tokens={run.draft}
            tokensShown={tokensShown}
            underlineFired={underlineFired}
            reduced={reduced}
          />
        </Block>

        <Block agent="critic" label="Critic" sub="verifies" active={activeAgent === 'critic'} last>
          <div
            className="mt-3 flex gap-2"
            style={{
              opacity: criticNoteVisible ? 1 : 0,
              transform: criticNoteVisible ? 'translateY(0)' : 'translateY(4px)',
              transition: reduced ? 'none' : 'opacity 380ms ease-out, transform 380ms ease-out',
            }}
          >
            <span
              className="font-mono text-sm leading-[1.5]"
              style={{ color: 'var(--critic)' }}
              aria-hidden
            >
              ◦
            </span>
            <span className="serif text-sm italic leading-[1.55] text-fg-2">{run.criticNote}</span>
          </div>
          <ConfidenceBar value={run.confidence} fired={confidenceFired} reduced={reduced} />
        </Block>
      </div>

      <div className="flex items-start gap-3.5">
        <div className="serif text-sm font-light leading-relaxed text-fg-2">
          A question travels <b>Scout → Scribe → Critic</b>, and comes back as a report you can
          defend.
        </div>
      </div>
    </aside>
  )
}

function QueryRow({
  query,
  progress,
  reduced,
}: {
  query: string
  progress: number
  reduced: boolean
}) {
  return (
    <div className="border-b border-line px-4 py-3 sm:px-5">
      <div className="micro mb-1.5 text-muted">Query</div>
      <div
        className="serif text-sm italic leading-snug text-fg sm:text-base"
        style={{
          opacity: progress,
          transition: reduced ? 'none' : 'opacity 400ms ease-out',
        }}
      >
        “{query}”
      </div>
    </div>
  )
}

function Block({
  agent,
  label,
  sub,
  active,
  last,
  children,
}: {
  agent: AgentKey
  label: string
  sub: string
  active: boolean
  last?: boolean
  children: ReactNode
}) {
  return (
    <div
      className={`px-4 py-3.5 sm:px-5 ${last ? '' : 'border-b border-line'}`}
      style={{
        background: active ? `var(--${agent}-soft)` : 'transparent',
        transition: 'background 480ms ease-out',
      }}
    >
      <div className="flex items-baseline gap-2">
        <span
          className="block h-2 w-2 -translate-y-[1px]"
          style={{ background: `var(--${agent})` }}
          aria-hidden
        />
        <span
          className="serif text-sm font-medium tracking-tight"
          style={{ color: `var(--${agent})` }}
        >
          {label}
        </span>
        <span className="font-mono text-xs uppercase tracking-[0.12em] text-muted">{sub}</span>
        {active && (
          <span className="ml-auto flex items-center gap-1.5" style={{ color: `var(--${agent})` }}>
            <span className="pulse-dot" aria-hidden />
            <span className="font-mono text-xs uppercase tracking-[0.14em]">working</span>
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function SourceLine({
  num,
  title,
  credibility,
  visible,
  reduced,
}: {
  num: number
  title: string
  credibility: number
  visible: boolean
  reduced: boolean
}) {
  return (
    <div
      className="flex items-baseline gap-2.5"
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(3px)',
        transition: reduced ? 'none' : 'opacity 320ms ease-out, transform 320ms ease-out',
      }}
    >
      <span className="font-mono text-xs text-muted">[{num}]</span>
      <span className="serif min-w-0 flex-1 truncate text-sm text-fg">{title}</span>
      <span className="font-mono text-xs text-fg-2">{credibility}%</span>
    </div>
  )
}

function DraftView({
  tokens,
  tokensShown,
  underlineFired,
  reduced,
}: {
  tokens: readonly DraftToken[]
  tokensShown: number
  underlineFired: boolean
  reduced: boolean
}) {
  // Walk tokens once; group consecutive redlined `w` tokens into a single
  // wrapper so the Critic's underline draws as one continuous span. The
  // underline uses a gradient background (rather than border-bottom) so
  // it survives line wrapping cleanly. The slash is driven by a single
  // CSS transition on background-size — boolean fired/not, fixed
  // duration — so it lands like a pen stroke, not a loading bar.
  const nodes: ReactNode[] = []
  let group: { startIdx: number; children: ReactNode[] } | null = null

  const flushGroup = () => {
    if (!group) return
    nodes.push(
      <span
        key={`r-${group.startIdx}`}
        style={{
          backgroundImage:
            'linear-gradient(transparent calc(100% - 2px), var(--critic) calc(100% - 2px))',
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'left bottom',
          backgroundSize: underlineFired ? '100% 100%' : '0% 100%',
          transition: reduced ? 'none' : 'background-size 460ms cubic-bezier(0.2, 0.9, 0.3, 1)',
        }}
      >
        {group.children}
      </span>,
    )
    group = null
  }

  tokens.forEach((tok, i) => {
    const visible = i < tokensShown
    const leadingSpace = needsLeadingSpace(tok, i)
    const isRedline = tok.kind === 'w' && tok.redline === true
    const tokenNode = renderToken(tok, i, visible)

    if (isRedline) {
      if (!group) {
        // Leading space sits outside the redline group so the underline
        // doesn't dangle a character to the left of the first word.
        if (leadingSpace) nodes.push(' ')
        group = { startIdx: i, children: [] }
        group.children.push(tokenNode)
      } else {
        if (leadingSpace) group.children.push(' ')
        group.children.push(tokenNode)
      }
    } else {
      flushGroup()
      if (leadingSpace) nodes.push(' ')
      nodes.push(tokenNode)
    }
  })
  flushGroup()

  return <p className="serif mt-3 text-sm font-light leading-[1.7] text-fg sm:text-sm">{nodes}</p>
}

function needsLeadingSpace(tok: DraftToken, i: number): boolean {
  if (i === 0) return false
  // Citation chips and punctuation always attach to the previous token.
  if (tok.kind === 'c' || tok.kind === 'p') return false
  // A word follows: it always needs a space, even if the previous token
  // was punctuation (e.g. ", with").
  return true
}

function renderToken(tok: DraftToken, idx: number, visible: boolean): ReactNode {
  const baseStyle: CSSProperties = {
    opacity: visible ? 1 : 0,
    transition: 'opacity 200ms ease-out',
  }
  if (tok.kind === 'c') {
    return (
      <sup
        key={idx}
        className="font-mono text-xs text-muted"
        style={{ ...baseStyle, letterSpacing: '0.04em', marginLeft: '1px' }}
      >
        [{tok.n}]
      </sup>
    )
  }
  return (
    <span key={idx} style={baseStyle}>
      {tok.text}
    </span>
  )
}

function ConfidenceBar({
  value,
  fired,
  reduced,
}: {
  value: number
  fired: boolean
  reduced: boolean
}) {
  // The verdict lands once, fast. Before the Critic stamps, the readout
  // shows a dash placeholder so it's clear nothing has been scored yet —
  // not a number that's slowly counting up.
  return (
    <div className="mt-4">
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="micro text-muted">Confidence</span>
        <span
          className="font-mono text-xs text-fg"
          style={{
            transition: reduced ? 'none' : 'color 220ms ease-out',
            color: fired ? 'var(--fg)' : 'var(--muted)',
          }}
        >
          {fired ? `${value}%` : '—'}
        </span>
      </div>
      <div
        className="relative h-[3px] w-full"
        style={{ background: 'var(--line-soft)' }}
        aria-hidden
      >
        <div
          className="absolute inset-y-0 left-0"
          style={{
            width: `${fired ? value : 0}%`,
            background: 'var(--critic)',
            transition: reduced ? 'none' : 'width 520ms cubic-bezier(0.2, 0.9, 0.3, 1)',
          }}
        />
      </div>
    </div>
  )
}
