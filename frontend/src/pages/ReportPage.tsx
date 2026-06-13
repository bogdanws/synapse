import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'
import { MarginPanel } from '../components/MarginPanel'
import { ReportSection } from '../components/ReportSection'
import { SourceRow } from '../components/SourceRow'
import { Button } from '../components/ui/Button'
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
  const [highlightedSourceId, setHighlightedSourceId] = useState<string | null>(null)
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scrollToSource = useCallback((id: string) => {
    setHighlightedSourceId(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    window.history.pushState(null, '', `#${id}`)
    if (highlightTimerRef.current !== null) {
      clearTimeout(highlightTimerRef.current)
    }
    highlightTimerRef.current = setTimeout(() => setHighlightedSourceId(null), 2000)
  }, [])

  useEffect(() => {
    return () => {
      if (highlightTimerRef.current !== null) {
        clearTimeout(highlightTimerRef.current)
      }
    }
  }, [])

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
      <AppNavbar
        className="report-nav"
        style={{ padding: '12px 28px', borderBottom: '1px solid var(--line)' }}
      >
        <div className="report-nav-meta">
          <SynapseBrandLink
            className="flex items-center gap-2.5 shrink-0"
            labelClassName="serif"
            labelStyle={{ fontSize: 16, fontWeight: 500 }}
          />
          <span className="report-nav-rule" style={{ background: 'var(--line)' }} aria-hidden />
          <span className="micro report-nav-brief">
            Brief #{jobId.slice(0, 8).toUpperCase()} · Delivered {formatDate(deliveredAt)}
          </span>
        </div>
        <div className="report-nav-actions">
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
        </div>
      </AppNavbar>

      {/* Masthead — border stays full-width; content is bounded so the headline
          doesn't sprawl on ultrawide viewports. */}
      <header style={{ borderBottom: '1px solid var(--fg)' }}>
        <div className="report-masthead-inner">
          <div className="micro" style={{ marginBottom: 24 }}>
            Synapse Report · {formatDate(deliveredAt)}
          </div>
          <h1
            className="serif report-title"
            style={{
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
            className="report-meta-grid"
            style={{ marginTop: 36, paddingTop: 20, borderTop: '1px solid var(--line-soft)' }}
          >
            <MetaItem label="Drafted by" value={report.model} />
            <MetaItem label="Audited by" value={annotations.model} />
            <MetaItem label="Sources consulted" value={`${report.sources.length} cited`} />
            <MetaItem label="Reading time" value={`${readingTime} min`} />
          </div>
        </div>
      </header>

      {/* Executive summary — bg-2 band stays full-width; inner div anchors the
          text to the same 1280px grid as the masthead and body sections. */}
      <section
        className="serif"
        style={{
          background: 'var(--bg-2)',
          borderBottom: '1px solid var(--line)',
        }}
      >
        <div className="report-summary-inner">
          <div className="micro" style={{ marginBottom: 14 }}>
            Executive summary
          </div>
          <p
            className="report-summary-text"
            style={{
              lineHeight: 1.4,
              fontWeight: 300,
              margin: 0,
              maxWidth: 760,
              letterSpacing: '-0.005em',
            }}
          >
            {report.summary_md}
          </p>
        </div>
      </section>

      {/* Body sections — one grid row per section so margin notes align.
          The row spans full width so the annotation rail stays anchored to the
          right edge, while the report copy is centered inside the main column. */}
      <div style={{ flex: 1 }}>
        {report.sections.map((section, i) => {
          const confidence = annotations.section_confidence.find(
            (sc) => sc.section_id === section.id,
          )
          const sectionFlags = annotations.claim_flags.filter((f) => f.section_id === section.id)
          return (
            <div
              className="report-row"
              key={section.id}
              style={{
                borderTop: i === 0 ? undefined : '1px solid var(--line-soft)',
              }}
            >
              <div className="report-main-cell">
                <div className="report-content-column">
                  <ReportSection
                    num={i + 1}
                    section={section}
                    claimFlags={sectionFlags}
                    sources={report.sources}
                    onSourceClick={scrollToSource}
                  />
                </div>
              </div>
              <aside
                className="report-aside scrollbar"
                style={{
                  background: 'var(--bg-2)',
                }}
              >
                <MarginPanel claimFlags={sectionFlags} confidence={confidence?.score} />
                {/* Fade sentinel: always sticks to the visible bottom of the scroll
                    container so overflowing content dissolves rather than hard-clips. */}
                <div
                  className="report-aside-fade"
                  aria-hidden
                  style={{
                    position: 'sticky',
                    bottom: 0,
                    height: 40,
                    marginTop: -40,
                    background: 'linear-gradient(to bottom, transparent, var(--bg-2))',
                    pointerEvents: 'none',
                  }}
                />
              </aside>
            </div>
          )
        })}

        {/* Sources section */}
        <div
          className="report-row report-sources-row"
          style={{
            borderTop: '1px solid var(--line-soft)',
          }}
        >
          <div className="report-main-cell">
            <section
              className="report-content-column"
              style={{
                paddingTop: 24,
                borderTop: '1px solid var(--fg)',
              }}
            >
              <div className="micro" style={{ marginBottom: 16 }}>
                References · {report.sources.length} sources cited
              </div>
              <ol
                className="report-sources-list"
                style={{
                  paddingLeft: 22,
                  fontFamily: 'var(--serif)',
                  fontSize: 12,
                  lineHeight: 1.55,
                }}
              >
                {report.sources.map((src, idx) => (
                  <SourceRow
                    key={src.id}
                    source={src}
                    index={idx}
                    highlighted={highlightedSourceId === src.id}
                  />
                ))}
              </ol>
            </section>
          </div>
          <aside className="report-sources-aside" style={{ background: 'var(--bg-2)' }} />
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
