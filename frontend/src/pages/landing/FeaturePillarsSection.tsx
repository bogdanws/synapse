import { FEATURE_PILLARS } from './landing-content'

export function FeaturePillarsSection() {
  return (
    <section className="border-b border-line px-6 py-16 sm:px-10 sm:py-20 lg:px-14 lg:py-[72px]">
      <div className="micro mb-3">§ What you get</div>
      <h2
        className="serif mb-12 font-normal tracking-tight lg:mb-14"
        style={{ fontSize: 'clamp(32px, 5.5vw, 56px)', letterSpacing: '-0.03em', margin: 0 }}
      >
        Built to be audited.
      </h2>
      <div className="mt-12 grid border-t border-fg sm:grid-cols-3">
        {FEATURE_PILLARS.map((f, i) => (
          <div
            key={f.title}
            className="flex flex-col border-b border-fg p-7 sm:p-8"
            style={{ borderRight: i < 2 ? '1px solid var(--line)' : undefined }}
          >
            <div
              className="serif mb-5 font-normal leading-tight tracking-tight"
              style={{ fontSize: 'clamp(22px, 2.5vw, 30px)', letterSpacing: '-0.025em' }}
            >
              {f.title}
            </div>
            <p className="serif text-base font-light leading-relaxed text-fg-2">{f.body}</p>
            <div className="mt-auto pt-6">
              <div className="micro">{f.tag}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
