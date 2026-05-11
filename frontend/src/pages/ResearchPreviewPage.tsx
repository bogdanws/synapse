import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate } from '@tanstack/react-router'

import { Button } from '../components/ui/Button'
import { SynapseMark } from '../components/ui/SynapseMark'
import { usePreviewResearch } from '../hooks/usePreviewResearch'
import { useStartResearch } from '../hooks/useStartResearch'
import { ALLOWED_MODELS } from '../constants/models'
import { ApiError } from '../services/api'
import { previewStateSchema, type PreviewState } from './researchPreviewState'

function modelLabel(id: string): string {
  return ALLOWED_MODELS.find((m) => m.id === id)?.label ?? id
}

const DEPTH_LABELS: Record<string, string> = {
  shallow: 'Shallow',
  standard: 'Standard',
  deep: 'Deep',
}

interface SubQRowProps {
  idx: number
  question: string
  isDropped: boolean
  onDrop: () => void
  onRestore: () => void
}

function SubQRow({ idx, question, isDropped, onDrop, onRestore }: SubQRowProps) {
  return (
    <li
      style={{
        display: 'grid',
        gridTemplateColumns: '32px 1fr auto',
        gap: 16,
        alignItems: 'center',
        padding: '16px 0',
        borderBottom: '1px solid var(--line-soft)',
        opacity: isDropped ? 0.45 : 1,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Drag handle is visual only for v1; DnD reordering is a future enhancement */}
        <span className="mono" style={{ fontSize: 10, color: 'var(--muted)', cursor: 'grab' }}>
          ⋮⋮
        </span>
        <span className="mono" style={{ fontSize: 11, color: 'var(--scout)' }}>
          S.{String(idx + 1).padStart(2, '0')}
        </span>
      </div>
      <div>
        <div
          className="serif"
          style={{
            fontSize: 17,
            lineHeight: 1.4,
            fontWeight: 400,
            textDecoration: isDropped ? 'line-through' : 'none',
          }}
        >
          {question}
        </div>
        {isDropped && (
          <div style={{ marginTop: 6 }}>
            <span
              className="mono"
              style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '0.12em' }}
            >
              DROPPED
            </span>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {/* Edit is deferred for now */}
        <button
          disabled
          style={{
            border: '1px solid var(--line)',
            background: 'transparent',
            padding: '4px 10px',
            fontFamily: 'var(--mono)',
            fontSize: 10,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--fg-2)',
            cursor: 'not-allowed',
            opacity: 0.4,
          }}
        >
          Edit
        </button>
        {isDropped ? (
          <button
            onClick={onRestore}
            style={{
              border: '1px solid var(--line)',
              background: 'transparent',
              padding: '4px 10px',
              fontFamily: 'var(--mono)',
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--fg-2)',
              cursor: 'pointer',
            }}
          >
            Restore
          </button>
        ) : (
          <button
            onClick={onDrop}
            style={{
              border: '1px solid var(--line)',
              background: 'transparent',
              padding: '4px 10px',
              fontFamily: 'var(--mono)',
              fontSize: 10,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--fg-2)',
              cursor: 'pointer',
            }}
          >
            Drop
          </button>
        )}
      </div>
    </li>
  )
}

interface ParamProps {
  label: string
  value: string
  hint?: string
  last?: boolean
}

function Param({ label, value, hint, last }: ParamProps) {
  return (
    <div style={{ padding: '10px 0', borderBottom: last ? 'none' : '1px solid var(--line-soft)' }}>
      <div className="micro" style={{ fontSize: 9 }}>
        {label}
      </div>
      <div
        className="serif"
        style={{ fontSize: 14, fontWeight: 400, marginTop: 3, letterSpacing: '-0.005em' }}
      >
        {value}
      </div>
      {hint && (
        <div className="mono" style={{ fontSize: 9, color: 'var(--muted)', marginTop: 3 }}>
          {hint}
        </div>
      )}
    </div>
  )
}

export default function ResearchPreviewPage() {
  const navigate = useNavigate()
  const location = useLocation()

  // Router-level `beforeLoad` already redirects on missing/invalid state, so
  // in production this parse always succeeds. The defensive fallback exists
  // for tests that render the component without a router and for the rare
  // case of a stale tab where the schema has drifted; the redirect runs from
  // an effect rather than during render to avoid a "state update during
  // render" warning under StrictMode.
  const rawState = (location.state ?? {}) as unknown
  const parsed = previewStateSchema.safeParse(rawState)

  useEffect(() => {
    if (!parsed.success) {
      void navigate({ to: '/research/new' })
    }
  }, [parsed.success, navigate])

  if (!parsed.success) {
    return null
  }

  return <PreviewContent initialState={parsed.data} />
}

function PreviewContent({ initialState }: { initialState: PreviewState }) {
  const navigate = useNavigate()
  const startResearch = useStartResearch()
  const previewResearch = usePreviewResearch()

  const [subQuestions, setSubQuestions] = useState<string[]>(initialState.subQuestions)
  const [dropped, setDropped] = useState<Set<number>>(new Set())
  const [launchError, setLaunchError] = useState<string | null>(null)

  const { formData } = initialState

  const keptCount = subQuestions.length - dropped.size
  const droppedCount = dropped.size

  const handleDrop = useCallback((idx: number) => {
    setDropped((prev) => new Set([...prev, idx]))
  }, [])

  const handleRestore = useCallback((idx: number) => {
    setDropped((prev) => {
      const next = new Set(prev)
      next.delete(idx)
      return next
    })
  }, [])

  const handleRegenerate = useCallback(async () => {
    try {
      const result = await previewResearch.mutateAsync({
        topic: formData.topic,
        depth: formData.depth,
        language: formData.language,
        models: formData.models,
      })
      setSubQuestions(result.sub_questions)
      setDropped(new Set())
    } catch {
      // Error is accessible via previewResearch.error for display
    }
  }, [previewResearch, formData])

  const handleLaunch = useCallback(async () => {
    setLaunchError(null)
    const kept = subQuestions.filter((_, i) => !dropped.has(i))
    if (kept.length === 0) {
      // Belt-and-braces: the launch button is disabled in this state, but a
      // direct keyboard activation could still fire. The backend currently
      // coerces `[]` to `None` (sub_questions_override falsy → re-decompose),
      // which would silently ignore the user's "drop everything" intent. Keep
      // the override decision client-side and surface an inline message.
      setLaunchError('Keep at least one sub-question, or go back to the brief.')
      return
    }
    try {
      const job = await startResearch.mutateAsync({
        topic: formData.topic,
        depth: formData.depth,
        language: formData.language,
        models: formData.models,
        // Pass only the questions the user approved so the worker skips Scout's
        // decompose step and uses this exact plan.
        sub_questions: kept,
      })
      try {
        localStorage.setItem('synapse:agent-models:v1', JSON.stringify(formData.models))
      } catch {
        // localStorage unavailable in private mode; non-fatal
      }
      await navigate({ to: '/research/$jobId', params: { jobId: job.id } })
    } catch (err) {
      if (err instanceof ApiError) {
        setLaunchError(err.message)
      } else {
        throw err
      }
    }
  }, [startResearch, formData, subQuestions, dropped, navigate])

  return (
    <div
      className="bg-bg text-fg"
      style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
    >
      {/* Top chrome */}
      <header
        style={{
          padding: '12px 28px',
          borderBottom: '1px solid var(--line)',
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 14,
        }}
      >
        <SynapseMark size={22} />
        <span className="serif" style={{ fontSize: 16, fontWeight: 500 }}>
          Synapse
        </span>
        <span style={{ width: 1, height: 16, background: 'var(--line)' }} />
        <span className="micro" style={{ color: 'var(--muted)' }}>
          New brief
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>
          ›
        </span>
        <span className="micro">Plan</span>
        <span className="mono hidden sm:inline" style={{ fontSize: 10, color: 'var(--muted)' }}>
          ›
        </span>
        <span className="micro hidden sm:inline" style={{ color: 'var(--muted)' }}>
          Run
        </span>
        <span className="mono hidden sm:inline" style={{ fontSize: 10, color: 'var(--muted)' }}>
          ›
        </span>
        <span className="micro hidden sm:inline" style={{ color: 'var(--muted)' }}>
          Report
        </span>
        <div
          className="sm:ml-auto"
          style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--scout)' }}
        >
          <span className="pulse-dot" />
          <span className="label">Scout has a plan — review before launch</span>
        </div>
      </header>

      {/* Topic restatement */}
      <div
        className="px-5 sm:px-10 lg:px-20"
        style={{ paddingTop: 32, paddingBottom: 20, borderBottom: '1px solid var(--line)' }}
      >
        <div className="micro" style={{ marginBottom: 10 }}>
          Your topic
        </div>
        <div
          className="serif"
          style={{
            fontSize: 32,
            lineHeight: 1.2,
            fontWeight: 300,
            letterSpacing: '-0.02em',
            maxWidth: 920,
          }}
        >
          &ldquo;{formData.topic}&rdquo;
        </div>
      </div>

      {/* Plan body */}
      <div
        className="px-5 sm:px-10 lg:px-20 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-10 lg:gap-14"
        style={{ paddingTop: 36, paddingBottom: 36, flex: 1 }}
      >
        {/* Left: sub-questions */}
        <div>
          <div
            className="flex flex-wrap items-baseline justify-between gap-y-3"
            style={{ marginBottom: 18 }}
          >
            <h2
              className="serif"
              style={{ fontSize: 32, fontWeight: 400, letterSpacing: '-0.02em', margin: 0 }}
            >
              Scout proposes{' '}
              <em>
                {keptCount} sub‑question{keptCount !== 1 ? 's' : ''}
              </em>
              .
            </h2>
            <div style={{ display: 'flex', gap: 8 }}>
              {/* Add question is deferred for now */}
              <Button variant="ghost" size="sm" disabled>
                + Add question
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={previewResearch.isPending}
                onClick={handleRegenerate}
              >
                {previewResearch.isPending ? 'Regenerating...' : 'Regenerate'}
              </Button>
            </div>
          </div>

          <div
            className="serif"
            style={{
              fontSize: 14.5,
              lineHeight: 1.55,
              color: 'var(--fg-2)',
              maxWidth: 720,
              marginBottom: 28,
              fontWeight: 300,
              fontStyle: 'italic',
            }}
          >
            Each will run as a parallel sub‑Scout. Reorder, rephrase, or drop any of them. Nothing
            is searched yet — Scout will only dispatch when you press{' '}
            <strong>Approve &amp; launch</strong>.
          </div>

          <ol
            aria-label="sub-questions"
            style={{ padding: 0, margin: 0, listStyle: 'none', borderTop: '1px solid var(--line)' }}
          >
            {subQuestions.map((q, i) => (
              <SubQRow
                key={i}
                idx={i}
                question={q}
                isDropped={dropped.has(i)}
                onDrop={() => handleDrop(i)}
                onRestore={() => handleRestore(i)}
              />
            ))}
          </ol>
        </div>

        {/* Right rail: run parameters */}
        <aside
          className="border-t pt-7 lg:border-t-0 lg:pt-0 lg:border-l lg:pl-7"
          style={{ borderColor: 'var(--line)' }}
        >
          <div className="micro" style={{ marginBottom: 14 }}>
            Run parameters
          </div>
          <Param label="Depth" value={DEPTH_LABELS[formData.depth] ?? formData.depth} />
          <div style={{ padding: '10px 0' }}>
            <div className="micro" style={{ fontSize: 9, marginBottom: 8 }}>
              Models
            </div>
            {Object.entries(formData.models).map(([agent, modelId]) => (
              <div
                key={agent}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  marginBottom: 5,
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'capitalize' }}
                >
                  {agent}
                </span>
                <span className="mono" style={{ fontSize: 12 }}>
                  {modelLabel(modelId)}
                </span>
              </div>
            ))}
          </div>

          {/* TODO: compute estimate from actual depth and question count once the backend exposes timing data */}
          <div
            style={{
              marginTop: 24,
              padding: '14px',
              background: 'var(--bg-2)',
              border: '1px solid var(--line)',
            }}
          >
            <div className="micro" style={{ marginBottom: 6 }}>
              Estimate
            </div>
            <div
              className="serif"
              style={{ fontSize: 28, fontWeight: 300, letterSpacing: '-0.02em', lineHeight: 1.05 }}
            >
              ~ 4 min
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6 }}>
              ~ 30–60 sources reviewed · ~80 claims to audit
            </div>
          </div>
        </aside>
      </div>

      {/* Footer launch bar */}
      <footer
        className="px-5 sm:px-10 lg:px-20 flex flex-wrap items-center gap-5"
        style={{
          paddingTop: 20,
          paddingBottom: 20,
          borderTop: '1px solid var(--fg)',
          background: 'var(--bg-2)',
        }}
      >
        <span className="micro">
          {keptCount} of {subQuestions.length} sub‑question{subQuestions.length !== 1 ? 's' : ''}{' '}
          selected · {droppedCount} dropped
        </span>
        {launchError && (
          <span className="text-[12px] text-critic" role="alert">
            {launchError}
          </span>
        )}
        <div className="ml-auto flex gap-2.5">
          <Button variant="ghost" onClick={() => void navigate({ to: '/research/new' })}>
            ← Back to brief
          </Button>
          <Button
            disabled={startResearch.isPending || keptCount === 0}
            onClick={() => void handleLaunch()}
          >
            {startResearch.isPending ? 'Launching...' : 'Approve & launch agents →'}
          </Button>
        </div>
      </footer>
    </div>
  )
}
