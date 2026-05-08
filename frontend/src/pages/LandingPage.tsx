import { useNavigate } from '@tanstack/react-router'

import { Button } from '../components/ui/Button'
import { SynapseMark } from '../components/ui/SynapseMark'
import { useMe } from '../hooks/useMe'

export default function LandingPage() {
  const user = useMe()
  const navigate = useNavigate()

  const ctaText = user ? 'Start a brief →' : 'Sign in'
  const ctaTo = user ? '/research/new' : '/login'

  return (
    <div className="min-h-screen bg-bg text-fg">
      {/* Top bar */}
      <header className="flex items-center justify-between px-14 py-6 border-b border-line">
        <div className="flex items-center gap-3.5">
          <SynapseMark size={28} />
          <span className="serif text-[22px] font-medium tracking-tight">Synapse</span>
          <span className="micro ml-3.5">v0.4 — private beta</span>
        </div>
        <nav className="flex items-center gap-8">
          <span className="label text-fg-2">Method</span>
          <span className="label text-fg-2">Agents</span>
          <span className="label text-fg-2">Reports</span>
          <Button size="sm" onClick={() => navigate({ to: ctaTo })}>
            {ctaText}
          </Button>
        </nav>
      </header>

      {/* Hero */}
      <section className="px-14 pt-[72px] pb-14 border-b border-line">
        <div className="max-w-[720px]">
          <div className="flex items-center gap-3 mb-8">
            <span className="micro">Issue 04 · May 2026</span>
            <span className="w-6 h-px bg-line" />
            <span className="micro">Three agents. One verified report.</span>
          </div>
          <h1 className="serif text-[clamp(48px,8vw,124px)] leading-[0.92] tracking-tight font-normal">
            Research that
            <br />
            <em className="font-light">fact‑checks</em>
            <br />
            itself.
          </h1>
          <p className="serif text-[22px] leading-snug text-fg-2 mt-9 max-w-[580px] font-light">
            Synapse pairs a researcher, a writer, and a sceptic — three specialised agents that
            draft, cite, and audit every claim before it lands on your desk.
          </p>
          <div className="flex gap-3 mt-10">
            <Button onClick={() => navigate({ to: ctaTo })}>{ctaText}</Button>
            <Button variant="ghost" onClick={() => navigate({ to: '/research/new' })}>
              Read a sample report
            </Button>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="px-14 py-[72px] border-b border-line">
        <div className="micro mb-3">§ Method</div>
        <h2 className="serif text-[56px] font-normal tracking-tight leading-none mb-14">
          From a question to a verified answer.
        </h2>
        <div className="grid grid-cols-5 gap-6">
          {[
            { n: '00', t: 'Brief', body: 'You write a topic and any constraints.' },
            {
              n: '01',
              t: 'Decompose & gather',
              body: 'Scout splits the question into sub-queries and pulls sources.',
            },
            {
              n: '02',
              t: 'Synthesise',
              body: 'Scribe drafts the report — sections, citations, summary.',
            },
            { n: '03', t: 'Audit', body: 'Critic re-reads every claim against its source.' },
            {
              n: '04',
              t: 'Delivered',
              body: 'You receive an annotated report with confidence scores.',
            },
          ].map((s) => (
            <div key={s.n}>
              <div className="micro mb-3.5">{s.n}</div>
              <div className="w-3.5 h-3.5 bg-fg mb-5" />
              <div className="serif text-[22px] font-medium tracking-tight mb-2">{s.t}</div>
              <div className="serif text-sm leading-relaxed text-fg-2 font-light">{s.body}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
