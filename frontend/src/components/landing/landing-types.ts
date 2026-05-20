export interface LandingCtaProps {
  ctaText: string
  onCtaClick: () => void
}

export interface LandingHeroProps extends LandingCtaProps {
  onSampleClick: () => void
}

export interface FooterCtaSectionProps {
  onSubmit: (email: string) => void
}
