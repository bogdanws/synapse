import type { FooterCtaSectionProps } from './landing-types'

export function FooterCtaSection({ onSubmit }: FooterCtaSectionProps) {
  return (
    <section
      id="pricing"
      className="bg-fg px-6 pb-12 pt-16 text-bg sm:px-10 sm:pt-20 lg:px-14 lg:pb-14 lg:pt-20"
    >
      <div className="grid gap-10 lg:grid-cols-[2fr_1fr] lg:items-end lg:gap-12">
        <h2
          className="serif m-0 font-light"
          style={{
            fontSize: 'clamp(40px, 8vw, 96px)',
            lineHeight: 0.95,
            letterSpacing: '-0.04em',
          }}
        >
          Ask a hard question.
          <br />
          <em>Get a defensible answer.</em>
        </h2>
        <div>
          <form
            className="mb-3 flex gap-2 border border-current p-1.5"
            onSubmit={(e) => {
              e.preventDefault()
              const formData = new FormData(e.currentTarget)
              const email = formData.get('email')
              if (typeof email === 'string') {
                onSubmit(email)
              }
            }}
          >
            <input
              name="email"
              type="email"
              required
              placeholder="your.email@firm.com"
              aria-label="Email"
              className="min-w-0 flex-1 border-0 bg-transparent px-3 py-2.5 font-sans text-sm text-inherit outline-none placeholder:text-current placeholder:opacity-60"
            />
            <button
              type="submit"
              className="shrink-0 cursor-pointer bg-bg px-4 py-2.5 font-sans text-[13px] text-fg sm:px-[18px]"
            >
              Sign up
            </button>
          </form>
        </div>
      </div>
    </section>
  )
}
