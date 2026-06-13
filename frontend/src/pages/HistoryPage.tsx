import { Link } from '@tanstack/react-router'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'
import { Button } from '../components/ui/Button'
import { Chip } from '../components/ui/Chip'
import type { Agent } from '../components/ui/Agent'
import { useResearchHistory } from '../hooks/useResearchHistory'
import type { JobStatus, JobSummary } from '../types/api'

const STATUS_META: Record<JobStatus, { agent: Agent; label: string }> = {
  completed: { agent: 'scout', label: 'completed' },
  pending: { agent: 'scribe', label: 'pending' },
  scouting: { agent: 'scribe', label: 'scouting' },
  synthesizing: { agent: 'scribe', label: 'synthesizing' },
  critiquing: { agent: 'scribe', label: 'critiquing' },
  failed: { agent: 'critic', label: 'failed' },
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function Shell({ children }: { children: React.ReactNode }) {
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
        <span className="label">Library</span>
      </AppNavbar>
      {children}
    </div>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        padding: 24,
      }}
    >
      {children}
    </div>
  )
}

export default function HistoryPage() {
  const { data, isLoading, isError, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useResearchHistory()

  if (isLoading) {
    return (
      <Shell>
        <Centered>
          <span className="serif" style={{ fontSize: 18, color: 'var(--muted)' }}>
            Loading library…
          </span>
        </Centered>
      </Shell>
    )
  }

  if (isError) {
    return (
      <Shell>
        <Centered>
          <span className="serif" style={{ fontSize: 18 }}>
            Could not load your library.
          </span>
          <Button variant="ghost" size="sm" onClick={() => void refetch()}>
            Try again
          </Button>
        </Centered>
      </Shell>
    )
  }

  const items = data?.pages.flatMap((p) => p.items) ?? []
  const total = data?.pages[0]?.total ?? 0

  if (items.length === 0) {
    return (
      <Shell>
        <Centered>
          <p className="micro">Library</p>
          <p
            className="serif"
            style={{
              fontSize: 28,
              fontWeight: 300,
              letterSpacing: '-0.02em',
              color: 'var(--fg-2)',
            }}
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
        </Centered>
      </Shell>
    )
  }

  return (
    <Shell>
      <div style={{ flex: 1 }}>
        <div className="mx-auto w-full" style={{ maxWidth: 860, padding: '40px 24px 64px' }}>
          <div className="micro" style={{ marginBottom: 24 }}>
            Library · {total} {total === 1 ? 'brief' : 'briefs'}
          </div>

          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {items.map((job) => (
              <HistoryRow key={job.id} job={job} />
            ))}
          </ul>

          {hasNextPage && (
            <div style={{ marginTop: 28, display: 'flex', justifyContent: 'center' }}>
              <Button
                variant="ghost"
                size="sm"
                disabled={isFetchingNextPage}
                onClick={() => void fetchNextPage()}
              >
                {isFetchingNextPage ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}
        </div>
      </div>
    </Shell>
  )
}

function HistoryRow({ job }: { job: JobSummary }) {
  const done = job.status === 'completed'
  const failed = job.status === 'failed'
  const status = STATUS_META[job.status]
  const confidencePct =
    job.overall_confidence != null ? Math.round(job.overall_confidence * 100) : null

  const meta = [formatDate(job.created_at)]
  if (done) {
    meta.push(`${job.source_count ?? 0} sources`)
    if (confidencePct != null) meta.push(`${confidencePct}% confidence`)
  }

  return (
    <li
      className="transition-colors hover:bg-bg-2"
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 16,
        padding: '18px 12px',
        margin: '0 -12px',
        borderTop: '1px solid var(--line-soft)',
        opacity: failed ? 0.6 : 1,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <Link
          to={done ? '/research/$jobId/report' : '/research/$jobId'}
          params={{ jobId: job.id }}
          className="serif"
          style={{
            display: 'block',
            fontSize: 18,
            fontWeight: 300,
            letterSpacing: '-0.01em',
            color: 'inherit',
            textDecoration: 'none',
            marginBottom: 6,
          }}
        >
          {job.topic}
        </Link>

        {job.parent_job_id && (
          <Link
            to="/research/$jobId/report"
            params={{ jobId: job.parent_job_id }}
            className="micro"
            style={{ color: 'var(--scribe)', textDecoration: 'none', display: 'inline-block' }}
            title={job.parent_topic ?? undefined}
          >
            ↳ Follow-up of “{truncate(job.parent_topic ?? 'a brief', 56)}”
          </Link>
        )}

        <div
          className="micro"
          style={{ color: 'var(--muted)', marginTop: job.parent_job_id ? 4 : 0 }}
        >
          {meta.join(' · ')}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        {job.parent_job_id && <Chip>↳ follow-up</Chip>}
        <Chip agent={status.agent} dot>
          {status.label}
        </Chip>
      </div>
    </li>
  )
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text
}
