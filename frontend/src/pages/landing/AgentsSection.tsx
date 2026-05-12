import { AGENT_CARDS } from './landing-content'

export function AgentsSection() {
  return (
    <section
      id="agents"
      className="border-b border-line px-6 py-16 sm:px-10 sm:py-20 lg:px-14 lg:py-[72px]"
    >
      <div className="mb-10 flex flex-col gap-6 sm:mb-12 md:flex-row md:items-baseline md:justify-between md:gap-10">
        <div>
          <div className="micro mb-3">§ Agents</div>
          <h2
            className="serif font-normal tracking-tight"
            style={{ fontSize: 'clamp(34px, 5.5vw, 56px)', letterSpacing: '-0.03em', margin: 0 }}
          >
            Three minds, one desk.
          </h2>
        </div>
        <div className="serif max-w-md text-base font-light italic leading-relaxed text-fg-2">
          Each agent is fine-tuned for a single craft. They hand off in sequence, but disagree on
          the page.
        </div>
      </div>

      <div className="grid border-t border-fg sm:grid-cols-2 lg:grid-cols-3">
        {AGENT_CARDS.map((a, i) => (
          <article
            key={a.key}
            className="flex min-h-[380px] flex-col border-b border-fg p-7 sm:p-8 lg:min-h-[420px]"
            style={{
              background: `var(--${a.key}-soft)`,
              borderRight: i < AGENT_CARDS.length - 1 ? '1px solid var(--line)' : undefined,
            }}
          >
            <div className="mb-7 flex items-start justify-between">
              <span className="serif text-sm italic text-muted">{a.num}</span>
              <span
                className={`agent-dot ${a.key}`}
                style={{ width: 36, height: 36, fontSize: 16 }}
              >
                {a.name[0]}
              </span>
            </div>
            <div
              className="serif font-normal leading-none tracking-tight"
              style={{ fontSize: 'clamp(34px, 4vw, 44px)', letterSpacing: '-0.03em' }}
            >
              {a.name}
            </div>
            <div className="label mt-2" style={{ color: `var(--${a.key})` }}>
              {a.role}
            </div>
            <p className="serif mt-5 text-base font-light leading-relaxed text-fg-2">{a.brief}</p>
            <div className="mt-auto border-t border-line pt-6">
              <div className="micro mb-2.5">Operations</div>
              {a.ops.map((op) => (
                <div key={op} className="font-mono py-[3px] text-[11px] text-fg-2">
                  <span style={{ color: `var(--${a.key})`, marginRight: 8 }}>→</span>
                  {op}
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
