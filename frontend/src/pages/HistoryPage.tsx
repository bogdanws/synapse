import { useState } from 'react'
import { Link } from '@tanstack/react-router'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'
import { Button } from '../components/ui/Button'
import { Chip } from '../components/ui/Chip'
import type { Agent } from '../components/ui/Agent'
import { useDeleteResearch } from '../hooks/useDeleteResearch'
import { useResearchHistory } from '../hooks/useResearchHistory'
import type { JobStatus, JobSummary } from '../types/api'

const STATUS_META: Record<JobStatus, { agent: Agent; label: string; active: boolean }> = {
  completed: { agent: 'scout', label: 'completed', active: false },
  failed: { agent: 'critic', label: 'failed', active: false },
  pending: { agent: 'scribe', label: 'pending', active: true },
  scouting: { agent: 'scribe', label: 'scouting', active: true },
  synthesizing: { agent: 'scribe', label: 'synthesizing', active: true },
  critiquing: { agent: 'scribe', label: 'critiquing', active: true },
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
        <Link
          to="/research/new"
          className="label"
          style={{ textDecoration: 'none', color: 'var(--muted)' }}
        >
          New brief
        </Link>
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
          <p className="micro">§ Library</p>
          <p
            className="serif"
            style={{
              fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
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
        <div className="mx-auto w-full" style={{ maxWidth: 900, padding: '0 24px 72px' }}>
          {/* Editorial page header, mirroring the landing's section grid: a §
           * micro-label over a large Fraunces headline, with a running tally
           * and a quick path back to composing on the right. */}
          <header
            className="grid gap-6 sm:grid-cols-[1fr_auto] sm:items-end"
            style={{ padding: '48px 0 28px' }}
          >
            <div>
              <div className="micro" style={{ marginBottom: 14 }}>
                § Library
              </div>
              <h1
                className="serif font-normal"
                style={{
                  fontSize: 'clamp(2.5rem, 6vw, 4rem)',
                  letterSpacing: '-0.035em',
                  lineHeight: 0.95,
                  margin: 0,
                }}
              >
                Everything you've
                <br />
                <em className="font-light">asked.</em>
              </h1>
            </div>
            <div className="flex items-baseline gap-4 sm:flex-col sm:items-end sm:gap-2">
              <span className="micro">
                {total} {total === 1 ? 'brief' : 'briefs'}
              </span>
              <Link
                to="/research/new"
                className="label"
                style={{ color: 'var(--fg)', textDecoration: 'underline', textUnderlineOffset: 4 }}
              >
                New brief →
              </Link>
            </div>
          </header>

          <ul
            style={{
              listStyle: 'none',
              padding: 0,
              margin: 0,
              borderTop: '1px solid var(--line)',
            }}
          >
            {items.map((job, i) => (
              <HistoryRow key={job.id} job={job} index={i + 1} />
            ))}
          </ul>

          {hasNextPage && (
            <div style={{ marginTop: 32, display: 'flex', justifyContent: 'center' }}>
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

function HistoryRow({ job, index }: { job: JobSummary; index: number }) {
  const done = job.status === 'completed'
  const failed = job.status === 'failed'
  const status = STATUS_META[job.status]
  const confidencePct =
    job.overall_confidence != null ? Math.round(job.overall_confidence * 100) : null

  const deleteResearch = useDeleteResearch()
  const [confirming, setConfirming] = useState(false)

  const meta = [formatDate(job.created_at)]
  if (done) {
    meta.push(`${job.source_count ?? 0} sources`)
    if (confidencePct != null) meta.push(`${confidencePct}% confidence`)
  }

  return (
    <li
      className="group relative transition-colors hover:bg-bg-2"
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 16,
        padding: '20px 12px',
        margin: '0 -12px',
        borderBottom: '1px solid var(--line-soft)',
        opacity: failed ? 0.6 : 1,
      }}
    >
      {/* Stretched link: a full-bleed overlay makes the whole row a single click
       * target to the report (or live progress). The nested follow-up link and
       * the delete controls sit above it via z-index so they stay independently
       * clickable — the standard "card link" pattern that keeps one primary
       * destination without nesting interactive elements inside an anchor. */}
      <Link
        to={done ? '/research/$jobId/report' : '/research/$jobId'}
        params={{ jobId: job.id }}
        aria-label={job.topic}
        className="absolute inset-0"
        style={{ zIndex: 0 }}
      />

      {/* Running index ties the list to the landing's numbered rails. */}
      <span
        className="font-mono shrink-0"
        style={{ fontSize: '0.6875rem', color: 'var(--muted)', paddingTop: 4, width: 22 }}
        aria-hidden
      >
        {String(index).padStart(2, '0')}
      </span>

      <div className="pointer-events-none" style={{ flex: 1, minWidth: 0 }}>
        <div
          className="serif"
          style={{
            fontSize: 20,
            fontWeight: 300,
            letterSpacing: '-0.015em',
            lineHeight: 1.2,
            color: 'inherit',
            marginBottom: 8,
          }}
        >
          {job.topic}
        </div>

        {job.parent_job_id && (
          <Link
            to="/research/$jobId/report"
            params={{ jobId: job.parent_job_id }}
            className="micro pointer-events-auto relative"
            style={{
              color: 'var(--scribe)',
              textDecoration: 'none',
              display: 'inline-block',
              zIndex: 1,
            }}
            title={job.parent_topic ?? undefined}
          >
            ↳ Follow-up of “{truncate(job.parent_topic ?? 'a brief', 56)}”
          </Link>
        )}

        <div className="flex items-center gap-2.5" style={{ marginTop: job.parent_job_id ? 6 : 0 }}>
          <span
            className={status.active ? 'pulse-dot' : ''}
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: `var(--${status.agent})`,
              flexShrink: 0,
            }}
            aria-hidden
          />
          <span className="micro" style={{ color: 'var(--muted)' }}>
            {meta.join(' · ')}
          </span>
        </div>
      </div>

      <div
        className="relative"
        style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, zIndex: 1 }}
      >
        {job.parent_job_id && <Chip>↳ follow-up</Chip>}
        <Chip agent={status.agent} dot>
          {status.label}
        </Chip>
        {confirming ? (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="micro" style={{ color: 'var(--muted)' }}>
              Delete?
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={deleteResearch.isPending}
              onClick={() => deleteResearch.mutate(job.id)}
              style={{ color: 'var(--critic)' }}
            >
              {deleteResearch.isPending ? 'Deleting…' : 'Yes'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={deleteResearch.isPending}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
          </span>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Delete ${job.topic}`}
            className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
            onClick={() => setConfirming(true)}
          >
            Delete
          </Button>
        )}
      </div>
    </li>
  )
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text
}
