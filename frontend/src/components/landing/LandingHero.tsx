import { Fragment, useMemo } from 'react'

import { useFontsReady } from '../../hooks/useFontsReady'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import { Button } from '../../components/ui/Button'

import { AgentPipelineHero } from './AgentPipelineHero'
import type { LandingHeroProps } from './landing-types'

// Print-magazine pacing: a brief lead-in delay, then ~38ms between words.
// Keeps the whole reveal under ~1s so it never holds up the page.
const WORD_STAGGER_MS = 38
const WORD_LEAD_IN_MS = 120

const LEDE =
  'Synapse runs three agents in parallel — one researches, one writes, one pushes back — so nothing reaches you unchecked.'

export function LandingHero({ ctaText, onCtaClick, onSampleClick }: LandingHeroProps) {
  const reduced = usePrefersReducedMotion()
  const fontsReady = useFontsReady()
  const words = useMemo(() => LEDE.split(/\s+/), [])

  return (
    <section className="flex flex-1 flex-col justify-center border-b border-line px-6 py-14 sm:px-10 sm:py-16 lg:px-14 lg:py-20">
      <div className="grid gap-10 lg:grid-cols-[1fr_26rem] lg:gap-14 xl:grid-cols-[1fr_30rem]">
        <div className="min-w-0">
          <h1
            className="serif font-normal tracking-tight"
            style={{
              fontSize: 'clamp(2.75rem, 11vw, 7.75rem)',
              lineHeight: 0.92,
              letterSpacing: '-0.04em',
              textWrap: 'balance',
              margin: 0,
            }}
          >
            Research that
            <br />
            <em className="font-light">fact-checks</em>
            <br />
            itself.
          </h1>
          <p className="hero-lede serif mt-8 max-w-xl text-lg font-light leading-snug text-fg-2 sm:mt-9 sm:text-xl lg:text-xl">
            {reduced || !fontsReady
              ? LEDE
              : words.map((word, i) => (
                  <Fragment key={i}>
                    <span
                      className="hero-word"
                      style={{
                        animationDelay: `${WORD_LEAD_IN_MS + i * WORD_STAGGER_MS}ms`,
                      }}
                    >
                      {word}
                    </span>
                    {i < words.length - 1 && ' '}
                  </Fragment>
                ))}
          </p>
          <div className="mt-8 flex flex-wrap gap-3 sm:mt-10">
            <Button onClick={onCtaClick}>{ctaText}</Button>
            <Button variant="ghost" onClick={onSampleClick}>
              Read a sample report
            </Button>
          </div>
        </div>

        <AgentPipelineHero />
      </div>
    </section>
  )
}
