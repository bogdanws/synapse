import { Button } from '../../components/ui/Button'

import { AgentConstellation } from './AgentConstellation'
import type { LandingHeroProps } from './landing-types'

export function LandingHero({ ctaText, onCtaClick, onSampleClick }: LandingHeroProps) {
  return (
    <section className="flex min-h-screen flex-col justify-center border-b border-line px-6 py-14 sm:px-10 sm:py-16 lg:px-14 lg:py-20">
      <div className="grid gap-10 lg:grid-cols-[1fr_420px] lg:gap-14 xl:grid-cols-[1fr_480px]">
        <div className="min-w-0">
          <h1
            className="serif font-normal tracking-tight"
            style={{
              fontSize: 'clamp(44px, 11vw, 124px)',
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
          <p className="serif mt-8 max-w-[580px] text-lg font-light leading-snug text-fg-2 sm:mt-9 sm:text-xl lg:text-[22px]">
            Synapse runs three agents in parallel — one researches, one writes, one pushes back — so
            nothing reaches you unchecked.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 sm:mt-10">
            <Button onClick={onCtaClick}>{ctaText}</Button>
            <Button variant="ghost" onClick={onSampleClick}>
              Read a sample report
            </Button>
          </div>
        </div>

        <AgentConstellation />
      </div>
    </section>
  )
}
