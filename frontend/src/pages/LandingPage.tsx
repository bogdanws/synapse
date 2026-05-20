import { useNavigate } from '@tanstack/react-router'

import { useMe } from '../hooks/useMe'

import { AgentsSection } from '../components/landing/AgentsSection'
import { FeaturePillarsSection } from '../components/landing/FeaturePillarsSection'
import { FooterCtaSection } from '../components/landing/FooterCtaSection'
import { LandingFooter } from '../components/landing/LandingFooter'
import { LandingHeader } from '../components/landing/LandingHeader'
import { LandingHero } from '../components/landing/LandingHero'
import { MethodSection } from '../components/landing/MethodSection'

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
