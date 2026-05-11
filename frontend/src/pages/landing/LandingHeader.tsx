import { SynapseMark } from '../../components/ui/SynapseMark'
import { Button } from '../../components/ui/Button'

import type { LandingCtaProps } from './landing-types'

export function LandingHeader({ ctaText, onCtaClick }: LandingCtaProps) {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-line px-6 py-5 sm:px-10 sm:py-6 lg:px-14">
      <div className="flex min-w-0 items-center gap-3 sm:gap-3.5">
        <SynapseMark size={28} />
        <span className="serif text-lg font-medium tracking-tight sm:text-[22px]">Synapse</span>
      </div>
      <nav className="flex items-center gap-4 sm:gap-6 lg:gap-8">
        <Button size="sm" onClick={onCtaClick}>
          {ctaText}
        </Button>
      </nav>
    </header>
  )
}
