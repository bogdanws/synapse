import { useEffect, useState } from 'react'
import { useNavigate, useParams } from '@tanstack/react-router'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'
import { PhaseRail } from '../components/PhaseRail'
import { PhaseShell } from '../components/PhaseShell'
import { SourcePill } from '../components/SourcePill'
import { Button } from '../components/ui/Button'
import { cn } from '../components/ui/cn'
import { useDerivedJobState } from '../hooks/useDerivedJobState'
import { useJobStream } from '../hooks/useJobStream'
import type { Verdict } from '../types/api/types.gen'

const REPORT_REDIRECT_DELAY_MS = 1500

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function verdictLabel(verdict: Verdict): string {
  switch (verdict) {
    case 'supported':
      return 'SUPPORTED'
    case 'partially_supported':
      return 'PARTIAL'
    case 'unsupported':
      return 'UNSUPPORTED'
    case 'contradicted':
      return 'CONTRADICTED'
    default: {
      const _exhaustive: never = verdict
      return String(_exhaustive)
    }
  }
}

function verdictColor(verdict: Verdict): string {
  switch (verdict) {
    case 'supported':
      return 'var(--scout)'
    case 'partially_supported':
      return 'var(--scribe)'
    case 'unsupported':
    case 'contradicted':
      return 'var(--critic)'
    default: {
      const _exhaustive: never = verdict
      void _exhaustive
      return 'var(--muted)'
    }
  }
}

export default function JobProgressPage() {
  const { jobId } = useParams({ from: '/research/$jobId' })
  const navigate = useNavigate()
  const { messages, status: wsStatus } = useJobStream(jobId)

  const derived = useDerivedJobState(messages)
  const {
    topic,
    currentPhase,
    subQuestions,
    sources,
    sections,
    claimFlags,
    overallConfidence,
    sourceCount,
    wordCount,
    claimCount,
    scoutComplete,
    scribeComplete,
    createdAt,
  } = derived

  const isTerminal = currentPhase === 'done' || currentPhase === 'failed'

  // nowMs is set by the interval callback so elapsed computation stays inside
  // state and doesn't call Date.now() as an impure expression during render.
  const [nowMs, setNowMs] = useState(() => Date.now())

  useEffect(() => {
    if (!createdAt || isTerminal) return
    const id = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [createdAt, isTerminal])

  const elapsedSeconds = createdAt
    ? Math.max(0, Math.floor((nowMs - new Date(createdAt).getTime()) / 1000))
    : 0

  const [completionMessage, setCompletionMessage] = useState<string | undefined>()

  useEffect(() => {
    if (currentPhase !== 'done') return
    // Defer the message update out of the synchronous effect body to avoid
    // cascading-render lint warnings; the 0ms delay still batches in the same
    // event loop turn but satisfies the rule.
    const msgId = setTimeout(() => setCompletionMessage('Report ready — opening...'), 0)
    const navId = setTimeout(() => {
      void navigate({ to: '/research/$jobId/report', params: { jobId } })
    }, REPORT_REDIRECT_DELAY_MS)
    return () => {
      clearTimeout(msgId)
      clearTimeout(navId)
    }
  }, [currentPhase, jobId, navigate])

  // Scout card —————————————————————————————————————————————

  const scoutStatus = scoutComplete ? 'done' : currentPhase === 'scout' ? 'active' : 'queue'

  const scoutTitle = scoutComplete
    ? 'Scout has gathered the evidence.'
    : currentPhase === 'scout'
      ? 'Scout is gathering evidence.'
      : 'Scout is waiting to start.'

  const scoutSummary = scoutComplete
    ? `${subQuestions.length} sub‑questions · ${sourceCount} sources kept`
    : subQuestions.length > 0
      ? `${subQuestions.length} sub‑questions · ${sourceCount} sources so far`
      : 'Decomposing the topic into sub‑questions…'

  // Scribe card ————————————————————————————————————————————

  const scribeStatus = scribeComplete ? 'done' : currentPhase === 'scribe' ? 'active' : 'queue'

  const scribeTitle = scribeComplete
    ? 'Scribe has drafted the report.'
    : currentPhase === 'scribe'
      ? 'Scribe is drafting the report.'
      : 'Scribe is waiting for Scout.'

  const scribeSummary = scribeComplete
    ? `${sections.length} sections · ~${wordCount.toLocaleString()} words`
    : currentPhase === 'scribe'
      ? `Reading ${sourceCount} sources from Scout · ${sections.length} sections drafted · ~${wordCount.toLocaleString()} words so far`
      : 'Will start once Scout finishes'

  // Critic card ————————————————————————————————————————————

  const criticStatus =
    currentPhase === 'done'
      ? 'done'
      : currentPhase === 'critic'
        ? 'active'
        : currentPhase === 'failed'
          ? 'done'
          : 'queue'

  const criticTitle =
    currentPhase === 'done' || currentPhase === 'failed'
      ? 'Critic has verified the claims.'
      : currentPhase === 'critic'
        ? 'Critic is verifying the claims.'
        : 'Critic is waiting for the draft.'

  const criticSummary =
    currentPhase === 'critic' || currentPhase === 'done' || currentPhase === 'failed'
      ? `${claimCount} claims verified${overallConfidence !== null ? ` · overall confidence .${Math.round(overallConfidence * 100)}` : ''}`
      : 'Will start once Scribe finishes · audits every claim against its source'

  // Status bar label ————————————————————————————————————————

  const isFailed = currentPhase === 'failed'
  const failedMessage = messages.find((m) => m.type === 'job_failed')

  const statusColor = isFailed
    ? 'var(--critic)'
    : currentPhase === 'done'
      ? 'var(--scout)'
      : 'var(--scribe)'

  const statusLabel = isFailed
    ? `Failed${failedMessage?.type === 'job_failed' ? ` — ${failedMessage.error}` : ''}`
    : currentPhase === 'done'
      ? 'Completed'
      : `In progress · ${formatElapsed(elapsedSeconds)} elapsed`

  // Compact status label for narrow viewports: keep the timer, drop extra text.
  const statusLabelShort = isFailed
    ? 'Failed'
    : currentPhase === 'done'
      ? 'Completed'
      : `In progress · ${formatElapsed(elapsedSeconds)}`

  return (
    <div
      className="flex flex-col min-h-screen"
      style={{ background: 'var(--bg)', color: 'var(--fg)' }}
    >
      {/* Brief bar */}
      <AppNavbar
        className="flex items-center gap-3 sm:gap-5 px-4 sm:px-7 py-3 sm:py-3.5 border-b shrink-0"
        style={{ borderColor: 'var(--line)' }}
      >
        <SynapseBrandLink
          className="flex items-center gap-2 sm:gap-2.5 shrink-0"
          labelClassName="serif hidden sm:inline-block"
          labelStyle={{ fontSize: 16, fontWeight: 500 }}
        />

        <span
          className="hidden sm:block w-px h-4 shrink-0"
          style={{ background: 'var(--line)' }}
          aria-hidden
        />

        <span className="micro hidden md:inline">Brief</span>

        <span
          className="serif flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap"
          style={{ fontSize: 14, fontStyle: 'italic', color: 'var(--fg-2)' }}
          title={topic ?? undefined}
        >
          {topic ? `"${topic}"` : 'Loading…'}
        </span>

        <div
          className="flex items-center gap-2 label shrink-0"
          style={{ color: statusColor }}
          aria-live="polite"
          aria-label="job status"
        >
          {!isTerminal && wsStatus === 'open' && <span className="pulse-dot" aria-hidden />}
          {/* Full label on md+, compact (no error reason / no "elapsed" word) on mobile. */}
          <span className="hidden md:inline">{statusLabel}</span>
          <span className="md:hidden">{statusLabelShort}</span>
        </div>

        {/* Cancel is a future capability; backend cancellation is not exposed yet. */}
        {/* TODO: wire up job cancellation endpoint */}
        <Button variant="ghost" size="sm" disabled className="hidden sm:inline-flex">
          Cancel
        </Button>
      </AppNavbar>

      {/* Connection-lost banner — muted stripe, non-intrusive */}
      {(wsStatus === 'error' || wsStatus === 'closed') && !isTerminal && (
        <div
          className="px-4 sm:px-7 py-2 text-center label"
          style={{
            background: 'var(--bg-2)',
            color: 'var(--muted)',
            borderBottom: '1px solid var(--line)',
          }}
          role="alert"
          aria-live="assertive"
        >
          Connection lost — results may be incomplete.
        </div>
      )}

      {/* Phase rail */}
      <PhaseRail
        currentPhase={currentPhase}
        scoutComplete={scoutComplete}
        scribeComplete={scribeComplete}
        completionMessage={completionMessage}
      />

      {/* Body — scrollable phase cards */}
      <div
        className={cn(
          'flex-1 overflow-auto min-h-0 scrollbar',
          'px-4 sm:px-7 lg:px-8 pt-6 sm:pt-7 pb-8 sm:pb-9',
        )}
      >
        {/* Scout card */}
        <PhaseShell
          agent="scout"
          stageNum="01"
          title={scoutTitle}
          summary={scoutSummary}
          status={scoutStatus}
          defaultOpen
        >
          <div className="mt-4 sm:mt-[18px]">
            {subQuestions.length > 0 ? (
              <>
                <div className="micro mb-3">
                  Scout fanned out — one parallel sub‑agent per question.
                </div>
                <div
                  className="grid grid-cols-1 md:grid-cols-2"
                  style={{ borderTop: '1px solid var(--line)' }}
                >
                  {subQuestions.map((q, i) => {
                    const isRightColumn = i % 2 === 1
                    return (
                      <div
                        key={i}
                        className={cn(
                          'border-b border-[var(--line-soft)] px-4 py-4 sm:px-[22px] sm:py-[18px]',
                          !isRightColumn && 'md:border-r md:border-r-[var(--line-soft)]',
                        )}
                      >
                        <div className="flex items-baseline gap-3 mb-2">
                          <span
                            className="font-mono shrink-0"
                            style={{ fontSize: 10, color: 'var(--scout)' }}
                          >
                            S.{String(i + 1).padStart(2, '0')}
                          </span>
                          <span
                            className="serif flex-1"
                            style={{ fontSize: 14.5, lineHeight: 1.35 }}
                          >
                            {q}
                          </span>
                        </div>
                        {sources.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2.5">
                            {/* Sources are not linked to individual sub-questions by the API, so all
                             * sources appear in the Scout card grouped by arrival order. */}
                            {sources.slice(0, 6).map((src) => (
                              <SourcePill
                                key={src.id}
                                title={src.title}
                                credibility={src.credibility}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </>
            ) : (
              <div
                className="micro text-center py-4"
                style={{ color: 'var(--muted)', borderTop: '1px solid var(--line-soft)' }}
              >
                Awaiting sub‑questions…
              </div>
            )}
          </div>
        </PhaseShell>

        {/* Scribe card */}
        <PhaseShell
          agent="scribe"
          stageNum="02"
          title={scribeTitle}
          summary={scribeSummary}
          status={scribeStatus}
          defaultOpen={scribeStatus !== 'queue'}
        >
          <div className="mt-4 sm:mt-[18px] grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-7 lg:gap-8">
            {/* Left: outline */}
            <div>
              <div className="micro mb-3">Outline</div>
              {sections.length > 0 ? (
                <ol className="list-none p-0 m-0">
                  {sections.map((sec, i) => {
                    // The last section that arrived is considered "active" while Scribe runs;
                    // once scribeComplete, all sections are "done".
                    const isLastAndActive = !scribeComplete && i === sections.length - 1
                    const sectionStatus = scribeComplete
                      ? 'done'
                      : isLastAndActive
                        ? 'active'
                        : 'done'
                    return (
                      <li
                        key={sec.id}
                        className="flex items-center gap-2.5 py-2"
                        style={{ borderTop: '1px solid var(--line-soft)' }}
                      >
                        <span
                          className="font-mono shrink-0"
                          style={{ fontSize: 10, color: 'var(--muted)', width: 24 }}
                        >
                          §{i + 1}
                        </span>
                        <span
                          className={cn(
                            'serif flex-1',
                            sectionStatus === 'done' && !isLastAndActive && 'line-through',
                          )}
                          style={{
                            fontSize: 13.5,
                            color: 'var(--fg)',
                            fontWeight: sectionStatus === 'active' ? 500 : 400,
                          }}
                        >
                          {sec.heading}
                        </span>
                        <span
                          className="font-mono"
                          style={{
                            fontSize: 9,
                            letterSpacing: '0.12em',
                            color: sectionStatus === 'active' ? 'var(--scribe)' : 'var(--muted)',
                          }}
                        >
                          {sectionStatus === 'active' ? 'WRITING' : '✓ DRAFTED'}
                        </span>
                      </li>
                    )
                  })}
                </ol>
              ) : (
                <div
                  className="micro py-4"
                  style={{ color: 'var(--muted)', borderTop: '1px solid var(--line-soft)' }}
                >
                  Awaiting first section…
                </div>
              )}
            </div>

            {/* Right: live draft of the latest section */}
            <div>
              {sections.length > 0 ? (
                <>
                  <div className="micro mb-2.5">
                    {scribeComplete
                      ? `Final section — ${sections[sections.length - 1]?.heading}`
                      : `Now writing · §${sections.length} — ${sections[sections.length - 1]?.heading}`}
                  </div>
                  <div
                    className="px-5 sm:px-[22px] py-5"
                    style={{
                      border: '1px solid var(--line)',
                      background: 'var(--bg-2)',
                    }}
                  >
                    <div
                      className="serif"
                      style={{ fontSize: 14, lineHeight: 1.6, fontWeight: 300 }}
                    >
                      {sections[sections.length - 1]?.body_md}
                    </div>
                  </div>
                </>
              ) : (
                <div className="micro py-4" style={{ color: 'var(--muted)' }}>
                  Awaiting first section…
                </div>
              )}
            </div>
          </div>
        </PhaseShell>

        {/* Critic card */}
        <PhaseShell
          agent="critic"
          stageNum="03"
          title={criticTitle}
          summary={criticSummary}
          status={criticStatus}
          defaultOpen={criticStatus !== 'queue'}
        >
          {criticStatus === 'queue' ? (
            <div
              className="mt-3.5 px-5 py-4"
              style={{
                background: 'var(--bg-2)',
                border: '1px dashed var(--line)',
              }}
            >
              <div
                className="serif"
                style={{
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: 'var(--fg-2)',
                  fontWeight: 300,
                  fontStyle: 'italic',
                }}
              >
                Critic runs strictly after Scribe — it needs the finished draft to audit. Expect
                claims to verify, with confidence scores per section and explicit flags for any
                unsupported sentences.
              </div>
            </div>
          ) : (
            <div className="mt-4 sm:mt-[18px]">
              {claimFlags.length > 0 ? (
                <ul className="list-none p-0 m-0">
                  {claimFlags.map((flag) => (
                    <li
                      key={flag.claim_id}
                      className="flex flex-col sm:flex-row sm:items-start gap-1.5 sm:gap-3 py-2.5"
                      style={{ borderTop: '1px solid var(--line-soft)' }}
                    >
                      <span
                        className="font-mono shrink-0 sm:pt-0.5"
                        style={{
                          fontSize: 9,
                          letterSpacing: '0.1em',
                          color: verdictColor(flag.verdict),
                          minWidth: 88,
                        }}
                      >
                        {verdictLabel(flag.verdict)}
                      </span>
                      <span
                        className="serif flex-1"
                        style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--fg-2)' }}
                      >
                        {flag.rationale}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div
                  className="micro py-4"
                  style={{ color: 'var(--muted)', borderTop: '1px solid var(--line-soft)' }}
                >
                  Verifying claims…
                </div>
              )}
            </div>
          )}
        </PhaseShell>
      </div>

      {/* Footer telemetry */}
      <footer
        className={cn(
          'shrink-0 border-t px-4 sm:px-7 py-2.5 sm:py-[10px]',
          'flex flex-wrap items-center gap-x-6 sm:gap-x-7 gap-y-2.5',
        )}
        style={{ background: 'var(--bg-2)', borderColor: 'var(--line)' }}
      >
        <TelemetryItem label="Sub‑questions" value={String(subQuestions.length)} />
        <TelemetryItem label="Sources read" value={String(sourceCount)} />
        <TelemetryItem
          label="Words drafted"
          value={wordCount > 0 ? wordCount.toLocaleString() : '—'}
        />
        <TelemetryItem label="Claims audited" value={String(claimCount)} />
        <div className="flex gap-x-6 sm:gap-x-7 w-full lg:w-auto lg:ml-auto">
          <TelemetryItem
            label="Stage"
            value={
              currentPhase === 'scout'
                ? '1 of 3 — Scout'
                : currentPhase === 'scribe'
                  ? '2 of 3 — Scribe'
                  : currentPhase === 'critic'
                    ? '3 of 3 — Critic'
                    : currentPhase === 'done'
                      ? 'Complete'
                      : currentPhase === 'failed'
                        ? 'Failed'
                        : '1 of 3'
            }
          />
          {/* TODO: estimated completion requires runtime telemetry from the backend; placeholder for now */}
          <TelemetryItem label="Est. completion" value="—" />
        </div>
      </footer>
    </div>
  )
}

function TelemetryItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="micro" style={{ fontSize: 9 }}>
        {label}
      </div>
      <div className="font-mono" style={{ fontSize: 13, marginTop: 2 }}>
        {value}
      </div>
    </div>
  )
}
