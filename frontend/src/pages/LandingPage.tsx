import { useNavigate } from '@tanstack/react-router'

import { useMe } from '../hooks/useMe'

import { AgentsSection } from './landing/AgentsSection'
import { FeaturePillarsSection } from './landing/FeaturePillarsSection'
import { FooterCtaSection } from './landing/FooterCtaSection'
import { LandingFooter } from './landing/LandingFooter'
import { LandingHeader } from './landing/LandingHeader'
import { LandingHero } from './landing/LandingHero'
import { MethodSection } from './landing/MethodSection'

export default function LandingPage() {
  const user = useMe()
  const navigate = useNavigate()

  const ctaText = user ? 'Start a brief →' : 'Sign in'
  const ctaTo = user ? '/research/new' : '/login'

  return (
    <div className="min-h-screen bg-bg text-fg">
      <LandingHeader ctaText={ctaText} onCtaClick={() => navigate({ to: ctaTo })} />
      <LandingHero
        ctaText={ctaText}
        onCtaClick={() => navigate({ to: ctaTo })}
        onSampleClick={() => navigate({ to: ctaTo })}
      />
      <AgentsSection />
      <MethodSection />
      <FeaturePillarsSection />
      <FooterCtaSection onSubmit={(email) => navigate({ to: '/register', search: { email } })} />
      <LandingFooter />
    </div>
  )
}
