import { Link } from '@tanstack/react-router'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'

/*
 * History placeholder. Full implementation will replace this with a paginated
 * list of past jobs fetched from GET /api/research, each showing topic,
 * status, overall confidence, and a link to the report.
 */
export default function HistoryPage() {
  return (
    <div
      className="bg-bg text-fg"
      style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
    >
      <AppNavbar
        className="rule"
        style={{ padding: '16px 32px', display: 'flex', alignItems: 'center', gap: 10 }}
      >
        <SynapseBrandLink
          markSize={22}
          labelClassName="serif"
          labelStyle={{ fontSize: 17, fontWeight: 500 }}
          style={{ display: 'flex', alignItems: 'center', gap: 10 }}
        />
        <span style={{ width: 1, height: 16, background: 'var(--line)', marginLeft: 8 }} />
        <span className="label" style={{ marginLeft: 8 }}>
          Library
        </span>
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
        <p className="micro">History — coming soon</p>
        <p
          className="serif"
          style={{ fontSize: 28, fontWeight: 300, letterSpacing: '-0.02em', color: 'var(--fg-2)' }}
        >
          Your library is empty.
        </p>
        <Link
          to="/research/new"
          className="label"
          style={{ color: 'var(--fg)', textDecoration: 'underline', textUnderlineOffset: 4 }}
        >
          Start a new brief →
        </Link>
      </div>
    </div>
  )
}
