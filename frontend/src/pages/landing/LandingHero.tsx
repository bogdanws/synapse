import { Button } from '../../components/ui/Button'

import { AgentConstellation } from './AgentConstellation'
import type { LandingHeroProps } from './landing-types'

export function LandingHero({ ctaText, onCtaClick, onSampleClick }: LandingHeroProps) {
  return (
    <section className="border-b border-line px-6 pb-12 pt-14 sm:px-10 sm:pt-16 lg:px-14 lg:pb-14 lg:pt-[72px]">
      <div className="grid gap-10 lg:grid-cols-[1fr_420px] lg:gap-14 xl:grid-cols-[1fr_480px]">
        <div className="min-w-0">
          <div className="mb-6 sm:mb-8">
            <span className="micro">Three agents. One verified report.</span>
          </div>
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
            Synapse pairs a researcher, a writer, and a sceptic — three specialised agents that
            draft, cite, and audit every claim before it lands on your desk.
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
