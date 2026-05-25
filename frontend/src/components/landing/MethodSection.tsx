import { METHOD_STEPS } from './landing-content'

/*
 * The five steps form a pipeline, so they read as stations on a rail.
 * At lg, an absolutely positioned 1px rule runs horizontally across the
 * grid; dots sit on it (masked by a 4px ring in the page background, so
 * the rule appears to pass through). Below lg, the rail disappears and
 * the steps stack as a vertical sequence.
 */

const RAIL_OFFSET = '2.75rem'

export function MethodSection() {
  return (
    <section
      id="method"
      className="border-b border-line px-6 py-24 sm:px-10 sm:py-28 lg:px-14 lg:py-32"
    >
      <header className="mb-16 grid gap-8 lg:mb-24 lg:grid-cols-[1fr_auto] lg:items-end lg:gap-16">
        <div>
          <div className="micro mb-5">§ Method</div>
          <h2
            className="serif font-normal"
            style={{
              fontSize: 'clamp(2.5rem, 7vw, 5.25rem)',
              letterSpacing: '-0.035em',
              lineHeight: 0.95,
              margin: 0,
            }}
          >
            From a question
            <br />
            to a <em className="font-light">verified</em> answer.
          </h2>
        </div>
        <p className="serif max-w-md text-lg font-light leading-snug text-fg-2 lg:text-right lg:text-xl">
          Five stations, one pipeline. <em>Every claim earns its place</em> before the report
          reaches you.
        </p>
      </header>

      <div className="relative">
        <div
          aria-hidden
          className="absolute left-0 right-0 hidden h-px bg-fg lg:block"
          style={{ top: RAIL_OFFSET }}
        />

        <ol className="grid grid-cols-1 gap-y-12 sm:grid-cols-2 sm:gap-x-10 lg:grid-cols-5 lg:gap-x-8">
          {METHOD_STEPS.map((s) => {
            const accent = s.who ? `var(--${s.who})` : 'var(--fg)'
            return (
              <li key={s.n} className="flex flex-col">
                <div className="micro" style={{ height: '0.875rem' }}>
                  {s.n}
                </div>

                <div className="relative mt-6 mb-9 h-3">
                  <span
                    aria-hidden
                    className="absolute left-0 top-1/2 block h-3 w-3 -translate-y-1/2 rounded-full ring-4 ring-bg"
                    style={{ background: accent }}
                  />
                </div>

                <h3
                  className="serif font-normal"
                  style={{
                    fontSize: 'clamp(1.375rem, 1.8vw, 1.625rem)',
                    letterSpacing: '-0.025em',
                    lineHeight: 1.05,
                    margin: 0,
                  }}
                >
                  {s.t}
                </h3>

                {s.who && (
                  <div className="label mt-3" style={{ color: accent }}>
                    via {s.who}
                  </div>
                )}

                <p className="serif mt-4 text-sm font-light leading-relaxed text-fg-2">{s.body}</p>
              </li>
            )
          })}
        </ol>
      </div>
    </section>
  )
}
