import { METHOD_STEPS } from './landing-content'

export function MethodSection() {
  return (
    <section
      id="method"
      className="border-b border-line px-6 py-16 sm:px-10 sm:py-20 lg:px-14 lg:py-[72px]"
    >
      <div className="micro mb-3">§ Method</div>
      <h2
        className="serif mb-12 font-normal tracking-tight lg:mb-14"
        style={{ fontSize: 'clamp(32px, 5.5vw, 56px)', letterSpacing: '-0.03em', margin: 0 }}
      >
        From a question to a verified answer.
      </h2>

      <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:mt-12 lg:grid-cols-5">
        {METHOD_STEPS.map((s) => (
          <div key={s.n} className="border-t border-fg pb-8 pt-6 pr-6 lg:pr-4">
            <div className="micro mb-3.5">{s.n}</div>
            <div
              className="mb-5 h-3.5 w-3.5"
              style={{ background: s.who ? `var(--${s.who})` : 'var(--fg)' }}
            />
            <div className="serif mb-2 text-xl font-medium tracking-tight">{s.t}</div>
            {s.who && (
              <div className="label mb-2.5" style={{ color: `var(--${s.who})` }}>
                {s.who}
              </div>
            )}
            <div className="serif text-sm font-light leading-relaxed text-fg-2">{s.body}</div>
          </div>
        ))}
      </div>
    </section>
  )
}
