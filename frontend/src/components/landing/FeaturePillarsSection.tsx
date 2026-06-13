import { Fragment } from 'react'

import { FEATURE_PILLARS, type PillarOwner } from './landing-content'

const NUMERALS = ['I.', 'II.', 'III.'] as const

function OwnerHandoff({ owners }: { owners: readonly PillarOwner[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {owners.map((o, i) => (
        <Fragment key={`${o.label}-${i}`}>
          {i > 0 && (
            <span aria-hidden className="font-mono text-xs text-fg-3">
              →
            </span>
          )}
          <span className={`chip ${o.agent ?? ''}`}>
            <span className="dot" />
            {o.label}
          </span>
        </Fragment>
      ))}
    </div>
  )
}

export function FeaturePillarsSection() {
  return (
    <section className="border-b border-line px-6 py-24 sm:px-10 sm:py-28 lg:px-14 lg:py-32">
      <header className="mb-16 grid gap-8 lg:mb-24 lg:grid-cols-[1fr_auto] lg:items-end lg:gap-16">
        <div>
          <div className="micro mb-5">§ What you get</div>
          <h2
            className="serif font-normal"
            style={{
              fontSize: 'clamp(2.5rem, 7vw, 5.25rem)',
              letterSpacing: '-0.035em',
              lineHeight: 0.95,
              margin: 0,
            }}
          >
            Built to be
            <br />
            <em className="font-light">defended.</em>
          </h2>
        </div>
        <p className="serif max-w-md text-lg font-light leading-snug text-fg-2 lg:text-right lg:text-xl">
          Three guarantees that travel with every report —
          <em> so you can show your work, not just your output.</em>
        </p>
      </header>

      <div className="grid border-t border-fg lg:grid-cols-3">
        {FEATURE_PILLARS.map((f, i) => (
          <article
            key={f.title}
            className="flex flex-col gap-8 border-b border-line py-10 last:border-b-0 sm:py-12 lg:gap-10 lg:border-b-0 lg:border-r lg:border-line lg:px-10 lg:py-14 lg:first:pl-0 lg:last:border-r-0 lg:last:pr-0"
          >
            <span
              className="serif font-light leading-none text-fg-3"
              style={{
                fontSize: 'clamp(4rem, 6vw, 6rem)',
                letterSpacing: '-0.05em',
              }}
            >
              {NUMERALS[i]}
            </span>

            <div>
              <h3
                className="serif font-normal"
                style={{
                  fontSize: 'clamp(1.75rem, 2.8vw, 2.375rem)',
                  letterSpacing: '-0.03em',
                  lineHeight: 1,
                  margin: 0,
                }}
              >
                {f.title}
              </h3>
              <div className="mt-5">
                <OwnerHandoff owners={f.owners} />
              </div>
            </div>

            <p className="serif text-base font-light leading-relaxed text-fg-2 lg:text-base">
              {f.body}
            </p>
          </article>
        ))}
      </div>
    </section>
  )
}
