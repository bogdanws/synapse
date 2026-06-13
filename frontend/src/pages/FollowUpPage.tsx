import { Link, useParams } from '@tanstack/react-router'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'

/*
 * Follow-up placeholder. Full implementation will render a topic input
 * pre-seeded with the parent job's topic, spawn a child job via
 * POST /api/research with a follow_up_of reference, and cross-link the two in
 * the UI.
 */
export default function FollowUpPage() {
  const { jobId } = useParams({ from: '/research/$jobId/follow-up' })

  return (
    <div
      className="bg-bg text-fg"
      style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
    >
      <AppNavbar variant="app" className="flex items-center gap-2.5 px-4 sm:px-8">
        <SynapseBrandLink
          className="flex items-center gap-2.5"
          markSize={22}
          labelClassName="serif"
          labelStyle={{ fontSize: 17, fontWeight: 500 }}
        />
        <span className="w-px h-4 shrink-0" style={{ background: 'var(--line)' }} aria-hidden />
        <span className="micro" style={{ color: 'var(--muted)' }}>
          Report
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>
          ›
        </span>
        <span className="label">Follow-up</span>
      </AppNavbar>

      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
        }}
      >
        <p className="micro">Follow-ups — coming soon</p>
        <p
          className="serif"
          style={{ fontSize: 28, fontWeight: 300, letterSpacing: '-0.02em', color: 'var(--fg-2)' }}
        >
          Child jobs and cross-linking aren&apos;t wired yet.
        </p>
        <Link
          to="/research/$jobId/report"
          params={{ jobId }}
          className="label"
          style={{ color: 'var(--fg)', textDecoration: 'underline', textUnderlineOffset: 4 }}
        >
          ← Back to report
        </Link>
      </div>
    </div>
  )
}
