import { AGENT_CARDS } from './landing-content'

export function AgentsSection() {
  return (
    <section
      id="agents"
      className="border-b border-line px-6 py-24 sm:px-10 sm:py-28 lg:px-14 lg:py-32"
    >
      <header className="mb-16 grid gap-8 lg:mb-24 lg:grid-cols-[1fr_auto] lg:items-end lg:gap-16">
        <div>
          <div className="micro mb-5">§ Agents</div>
          <h2
            className="serif font-normal"
            style={{
              fontSize: 'clamp(2.5rem, 7vw, 5.25rem)',
              letterSpacing: '-0.035em',
              lineHeight: 0.95,
              margin: 0,
            }}
          >
            Three minds,
            <br />
            <em className="font-light">one desk.</em>
          </h2>
        </div>
        <p className="serif max-w-md text-lg font-light leading-snug text-fg-2 lg:text-right lg:text-xl">
          Each agent is fine-tuned for a single craft. They hand off in sequence —
          <em> and disagree on the page.</em>
        </p>
      </header>

      <div className="grid border-t border-fg lg:grid-cols-3">
        {AGENT_CARDS.map((a) => (
          <article
            key={a.key}
            className="flex flex-col gap-8 border-b border-line py-10 last:border-b-0 sm:py-12 lg:gap-10 lg:border-b-0 lg:border-r lg:border-line lg:px-10 lg:py-14 lg:first:pl-0 lg:last:border-r-0 lg:last:pr-0"
          >
            <header className="flex items-start justify-between gap-6">
              <span
                className="serif font-light leading-none"
                style={{
                  color: `var(--${a.key})`,
                  fontSize: 'clamp(4rem, 6vw, 6rem)',
                  letterSpacing: '-0.05em',
                }}
              >
                {a.num}
              </span>
              <span
                aria-hidden
                className={`agent-dot ${a.key} mt-2`}
                style={{ width: '2.5rem', height: '2.5rem', fontSize: '1.0625rem' }}
              >
                {a.name[0]}
              </span>
            </header>

            <div>
              <h3
                className="serif font-normal"
                style={{
                  fontSize: 'clamp(2.25rem, 3.6vw, 3.25rem)',
                  letterSpacing: '-0.035em',
                  lineHeight: 0.95,
                  margin: 0,
                }}
              >
                {a.name}
              </h3>
              <div className="label mt-3" style={{ color: `var(--${a.key})` }}>
                {a.role}
              </div>
              <div
                aria-hidden
                className="mt-6 h-px w-12"
                style={{ background: `var(--${a.key})` }}
              />
            </div>

            <p className="serif text-base font-light leading-relaxed text-fg-2 lg:text-base">
              {a.brief}
            </p>

            <div className="mt-auto">
              <div className="micro mb-5">Operations</div>
              <ol className="space-y-2.5">
                {a.ops.map((op, idx) => (
                  <li
                    key={op}
                    className="font-mono grid grid-cols-[1.75rem_1fr] gap-3 text-xs leading-snug text-fg-2"
                  >
                    <span className="tabular-nums text-fg-3">
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                    <span>{op}</span>
                  </li>
                ))}
              </ol>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
