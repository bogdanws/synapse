import { Link, useParams } from '@tanstack/react-router'

import { MarginPanel } from '../components/MarginPanel'
import { ReportSection } from '../components/ReportSection'
import { Button } from '../components/ui/Button'
import { Chip } from '../components/ui/Chip'
import { SynapseMark } from '../components/ui/SynapseMark'
import { useReport } from '../hooks/useReport'
import { ApiError } from '../services/api'

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

function estimateReadingTime(sections: { body_md: string }[]): number {
  const words = sections.reduce((n, s) => n + s.body_md.split(/\s+/).length, 0)
  return Math.max(1, Math.round(words / 200))
}

export default function ReportPage() {
  const { jobId } = useParams({ from: '/research/$jobId/report' })
  const { data, isLoading, error } = useReport(jobId)

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        style={{ background: 'var(--bg)', color: 'var(--muted)' }}
      >
        <span className="serif" style={{ fontSize: 18 }}>
          Loading report…
        </span>
      </div>
    )
  }

  if (error || !data) {
    const isNotReady = error instanceof ApiError && error.status === 404
    return (
      <div
        className="flex flex-col items-center justify-center min-h-screen gap-4"
        style={{ background: 'var(--bg)', color: 'var(--fg)' }}
      >
        <span className="serif" style={{ fontSize: 18 }}>
          {isNotReady
            ? 'Report is being prepared — check back shortly.'
            : 'Could not load the report.'}
        </span>
        <Link
          to="/research/$jobId"
          params={{ jobId }}
          className="micro"
          style={{ color: 'var(--scribe)' }}
        >
          ← Back to progress view
        </Link>
      </div>
    )
  }

  const { report, annotations, job } = data
  const deliveredAt = job.completed_at ? new Date(job.completed_at) : new Date()
  const readingTime = estimateReadingTime(report.sections)

  return (
    <div
      className="flex flex-col min-h-screen"
      style={{ background: 'var(--bg)', color: 'var(--fg)' }}
    >
      {/* App chrome */}
      <div
        className="flex items-center gap-5 shrink-0"
        style={{ padding: '12px 28px', borderBottom: '1px solid var(--line)' }}
      >
        <div className="flex items-center gap-2.5">
          <SynapseMark />
          <span className="serif" style={{ fontSize: 16, fontWeight: 500 }}>
            Synapse
          </span>
        </div>
        <span
          className="w-px h-4 block shrink-0"
          style={{ background: 'var(--line)' }}
          aria-hidden
        />
        <span className="micro">
          Brief #{jobId.slice(0, 8).toUpperCase()} · Delivered {formatDate(deliveredAt)}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Chip agent="scout" dot>
            Verified
          </Chip>
          <Button
            variant="ghost"
            size="sm"
            style={{ padding: '6px 12px', fontSize: 11 }}
            onClick={() => {
              window.location.href = `/api/research/${jobId}/export/markdown`
            }}
          >
            Export · Markdown
          </Button>
          <Button
            variant="ghost"
            size="sm"
            style={{ padding: '6px 12px', fontSize: 11 }}
            onClick={() => {
              window.location.href = `/api/research/${jobId}/export/pdf`
            }}
          >
            Export · PDF
          </Button>
          <Link to="/research/$jobId/follow-up" params={{ jobId }}>
            <Button size="sm" style={{ padding: '6px 12px', fontSize: 11 }}>
              Ask follow-up →
            </Button>
          </Link>
        </div>
      </div>

      {/* Masthead */}
      <header style={{ padding: '56px 88px 32px', borderBottom: '1px solid var(--fg)' }}>
        <div className="micro" style={{ marginBottom: 24 }}>
          Synapse Report · {formatDate(deliveredAt)}
        </div>
        <h1
          className="serif"
          style={{
            fontSize: 80,
            lineHeight: 0.95,
            letterSpacing: '-0.035em',
            fontWeight: 300,
            margin: 0,
            textWrap: 'balance',
          }}
        >
          {report.title}
        </h1>
        <div
          className="flex gap-12"
          style={{ marginTop: 36, paddingTop: 20, borderTop: '1px solid var(--line-soft)' }}
        >
          <MetaItem label="Drafted by" value={report.model} />
          <MetaItem label="Audited by" value={annotations.model} />
          <MetaItem label="Sources consulted" value={`${report.sources.length} cited`} />
          <MetaItem label="Reading time" value={`${readingTime} min`} />
        </div>
      </header>

      {/* Executive summary */}
      <section
        className="serif"
        style={{
          padding: '40px 88px',
          background: 'var(--bg-2)',
          borderBottom: '1px solid var(--line)',
        }}
      >
        <div className="micro" style={{ marginBottom: 14 }}>
          Executive summary
        </div>
        <p
          style={{
            fontSize: 24,
            lineHeight: 1.4,
            fontWeight: 300,
            margin: 0,
            maxWidth: 920,
            letterSpacing: '-0.005em',
          }}
        >
          {report.summary_md}
        </p>
      </section>

      {/* Body sections — one grid row per section so margin notes align */}
      <div style={{ flex: 1 }}>
        {report.sections.map((section, i) => {
          const confidence = annotations.section_confidence.find(
            (sc) => sc.section_id === section.id,
          )
          const sectionFlags = annotations.claim_flags.filter((f) => f.section_id === section.id)
          return (
            <div
              key={section.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 280px',
                borderTop: i === 0 ? undefined : '1px solid var(--line-soft)',
              }}
            >
              <div
                style={{
                  padding: '56px 56px 56px 88px',
                  borderRight: '1px solid var(--line)',
                }}
              >
                <ReportSection
                  num={i + 1}
                  section={section}
                  confidence={confidence}
                  claimFlags={sectionFlags}
                />
              </div>
              <aside style={{ background: 'var(--bg-2)' }}>
                <MarginPanel section={section} sources={report.sources} claimFlags={sectionFlags} />
              </aside>
            </div>
          )
        })}

        {/* Sources section */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 280px',
            borderTop: '1px solid var(--line-soft)',
          }}
        >
          <div style={{ padding: '56px 56px 56px 88px', borderRight: '1px solid var(--line)' }}>
            <section style={{ paddingTop: 24, borderTop: '1px solid var(--fg)' }}>
              <div className="micro" style={{ marginBottom: 16 }}>
                References · {report.sources.length} sources cited
              </div>
              <ol
                style={{
                  paddingLeft: 22,
                  fontFamily: 'var(--serif)',
                  fontSize: 12,
                  lineHeight: 1.55,
                  columns: 2,
                  columnGap: 32,
                }}
              >
                {report.sources.map((src, idx) => (
                  <li key={src.id} style={{ paddingBottom: 4, breakInside: 'avoid' }}>
                    <a href={src.url} target="_blank" rel="noreferrer" style={{ color: 'inherit' }}>
                      [{idx + 1}] {src.title}
                    </a>
                  </li>
                ))}
              </ol>
            </section>
          </div>
          <aside style={{ background: 'var(--bg-2)' }} />
        </div>
      </div>
    </div>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="micro" style={{ marginBottom: 4 }}>
        {label}
      </div>
      <div className="sans" style={{ fontSize: 13, fontWeight: 500 }}>
        {value}
      </div>
    </div>
  )
}
