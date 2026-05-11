import { useRef, useEffect, useCallback } from 'react'
import { useForm, type SubmitHandler } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { Button } from '../components/ui/Button'
import { SynapseMark } from '../components/ui/SynapseMark'
import { AGENTS, AGENT_ORDER, type Agent } from '../components/ui/Agent'
import { Pill } from '../components/Pill'
import { ConfidenceBar } from '../components/ConfidenceBar'
import { useMe } from '../hooks/useMe'
import { useAgentModels } from '../hooks/useAgentModels'
import { usePreviewResearch } from '../hooks/usePreviewResearch'
import { useResearchHistory } from '../hooks/useResearchHistory'
import { useStartResearch } from '../hooks/useStartResearch'
import { ApiError } from '../services/api'
import { ALLOWED_MODELS } from '../constants/models'

const allowedModelIds: string[] = ALLOWED_MODELS.map((m) => m.id)

const formSchema = z.object({
  topic: z.string().min(10, 'Topic must be at least 10 characters').max(2000),
  depth: z.enum(['shallow', 'standard', 'deep']),
  language: z.string(),
  models: z
    .object({
      scout: z.string(),
      scribe: z.string(),
      critic: z.string(),
    })
    .refine((vals) => Object.values(vals).every((v: string) => allowedModelIds.includes(v)), {
      message: 'Invalid model selection',
    }),
})

type FormData = z.infer<typeof formSchema>

const EXAMPLE_QUESTIONS = [
  "What's the current state of evidence on GLP-1 agonists and cardiovascular outcomes in non-diabetic patients?",
  'How did the EU AI Act risk tiers evolve between the 2021 draft and final passage, and who pushed which changes?',
  "Who controls the world's lithium refining capacity, and how has that concentration shifted since 2020?",
  'Heat pump adoption: what is working in the Nordics that is not translating to the UK, and why?',
]

const DEPTH_LABELS: Record<FormData['depth'], string> = {
  shallow: 'Shallow',
  standard: 'Standard',
  deep: 'Deep',
}

function getInitials(email: string): string {
  return email.split('@')[0].slice(0, 2).toUpperCase()
}

function formatNow(): string {
  const d = new Date()
  const date = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  return `New brief · ${date} · ${time}`
}

export default function ResearchInputPage() {
  const navigate = useNavigate()
  const me = useMe()
  const { models, setModel, persist } = useAgentModels()
  const history = useResearchHistory()
  const startResearch = useStartResearch()
  const previewResearch = usePreviewResearch()

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      topic: '',
      depth: 'standard',
      language: 'en',
      models,
    },
  })

  /* RHF's `watch` is intentionally un-memoised: it returns a fresh function on every render so subscribers stay in sync. The React Compiler eslint plugin flags the first call as "incompatible library" and skips compiling the rest of the hook, which is the behaviour we want here. */
  // eslint-disable-next-line react-hooks/incompatible-library
  const topicValue = watch('topic')
  const depthValue = watch('depth')

  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 400)}px`
  }, [topicValue])

  const onSubmit: SubmitHandler<FormData> = useCallback(
    async (data) => {
      try {
        const job = await startResearch.mutateAsync({
          topic: data.topic.trim(),
          depth: data.depth,
          language: data.language,
          models: data.models,
        })
        persist()
        await navigate({ to: '/research/$jobId', params: { jobId: job.id } })
      } catch (err) {
        // ApiError with 422 or 429 is rendered inline near the CTA.
        if (!(err instanceof ApiError)) {
          throw err
        }
      }
    },
    [startResearch, persist, navigate],
  )

  const handleModelChange = useCallback(
    (agent: Agent, modelId: string) => {
      setModel(agent, modelId)
      setValue(`models.${agent}`, modelId, { shouldValidate: true })
    },
    [setModel, setValue],
  )

  const handleExampleClick = useCallback(
    (question: string) => {
      setValue('topic', question, { shouldValidate: true })
    },
    [setValue],
  )

  const onPreview: SubmitHandler<FormData> = useCallback(
    async (data) => {
      try {
        const result = await previewResearch.mutateAsync({
          topic: data.topic.trim(),
          depth: data.depth,
          language: data.language,
          models: data.models,
        })
        await navigate({
          to: '/research/preview',
          state: (prev) => ({ ...prev, formData: data, subQuestions: result.sub_questions }),
        })
      } catch (err) {
        if (!(err instanceof ApiError)) {
          throw err
        }
      }
    },
    [previewResearch, navigate],
  )

  const briefCount = history.data?.length ?? 0

  const submitError = startResearch.error
  const showErrorInline =
    submitError instanceof ApiError && (submitError.status === 422 || submitError.status === 429)

  const previewError = previewResearch.error
  const showPreviewErrorInline =
    previewError instanceof ApiError && (previewError.status === 422 || previewError.status === 429)

  const { ref: topicRef, ...topicRest } = register('topic')

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: 'var(--bg)', color: 'var(--fg)' }}
    >
      {/* App chrome */}
      <header
        className="flex items-center justify-between px-8 py-4 shrink-0"
        style={{ borderBottom: '1px solid var(--line)' }}
      >
        <div className="flex items-center gap-7">
          <div className="flex items-center gap-2.5">
            <SynapseMark size={28} />
            <span
              className="serif"
              style={{ fontSize: 17, fontWeight: 500, letterSpacing: '-0.01em' }}
            >
              Synapse
            </span>
          </div>
          <nav className="flex gap-[18px]">
            <span className="label">New brief</span>
            <Link
              to="/history"
              className="label"
              style={{ textDecoration: 'none', color: 'var(--muted)' }}
            >
              Library
            </Link>
            <span className="label" style={{ color: 'var(--muted)' }}>
              Sources
            </span>
            <span className="label" style={{ color: 'var(--muted)' }}>
              Settings
            </span>
          </nav>
        </div>
        <div className="flex items-center gap-3.5">
          <span className="micro">
            {/* TODO: replace hard-coded 50 with a backend setting when available. */}
            {briefCount} / 50 briefs this month
          </span>
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center serif"
            style={{ background: 'var(--bg-3)', fontSize: 13 }}
            aria-label="user avatar"
          >
            {me ? getInitials(me.email) : ''}
          </div>
        </div>
      </header>

      {/* Main */}
      <div className="flex-1 grid overflow-hidden" style={{ gridTemplateColumns: '1fr 320px' }}>
        {/* Composition column */}
        <main className="flex flex-col overflow-auto" style={{ padding: '60px 80px' }}>
          <div className="micro" style={{ marginBottom: 16 }}>
            {formatNow()}
          </div>
          <h1
            className="serif m-0"
            style={{
              fontSize: 64,
              lineHeight: 1,
              letterSpacing: '-0.03em',
              fontWeight: 300,
            }}
          >
            What would you like
            <br />
            to <em>understand</em>?
          </h1>

          {/* Topic card */}
          <div
            style={{
              marginTop: 48,
              border: '1px solid var(--fg)',
              padding: 24,
              background: 'var(--bg-2)',
            }}
          >
            <div className="label" style={{ marginBottom: 12, color: 'var(--muted)' }}>
              Topic
            </div>
            <textarea
              {...topicRest}
              ref={(el) => {
                topicRef(el)
                textareaRef.current = el
              }}
              placeholder="Type your research topic here..."
              rows={1}
              className="serif w-full bg-transparent outline-none resize-none overflow-hidden"
              style={{
                fontSize: 28,
                lineHeight: 1.3,
                fontWeight: 300,
                color: 'var(--fg)',
                minHeight: 80,
                letterSpacing: '-0.005em',
              }}
            />

            {/* Controls row — depth + three agent model selectors, actions on the right. */}
            <div
              className="flex flex-wrap items-center gap-3"
              style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid var(--line)' }}
            >
              <Pill
                label="Depth"
                value={
                  <select
                    value={depthValue}
                    onChange={(e) => setValue('depth', e.target.value as FormData['depth'])}
                    className="bg-transparent font-sans text-[12px] cursor-pointer outline-none"
                    aria-label="Research depth"
                  >
                    <option value="shallow">{DEPTH_LABELS.shallow}</option>
                    <option value="standard">{DEPTH_LABELS.standard}</option>
                    <option value="deep">{DEPTH_LABELS.deep}</option>
                  </select>
                }
                interactive
              />

              {AGENT_ORDER.map((agent) => (
                <Pill
                  key={agent}
                  label={AGENTS[agent].name}
                  agent={agent}
                  value={
                    <select
                      value={models[agent]}
                      onChange={(e) => handleModelChange(agent, e.target.value)}
                      className="bg-transparent font-sans text-[12px] cursor-pointer outline-none max-w-[140px]"
                      aria-label={`${AGENTS[agent].name} model`}
                    >
                      {ALLOWED_MODELS.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  }
                  interactive
                />
              ))}

              <div className="ml-auto flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={previewResearch.isPending}
                  onClick={handleSubmit(onPreview)}
                >
                  {previewResearch.isPending ? 'Generating plan…' : 'Preview plan →'}
                </Button>
                <Button
                  size="sm"
                  onClick={handleSubmit(onSubmit)}
                  disabled={startResearch.isPending}
                >
                  {startResearch.isPending ? 'Starting…' : 'Start brief →'}
                </Button>
              </div>
            </div>

            {(errors.topic || showErrorInline || showPreviewErrorInline) && (
              <div className="flex flex-col gap-1" style={{ marginTop: 14 }}>
                {errors.topic && (
                  <span
                    className="micro"
                    role="alert"
                    style={{ color: 'var(--critic)', letterSpacing: '0.08em' }}
                  >
                    {errors.topic.message}
                  </span>
                )}
                {showErrorInline && (
                  <span
                    className="micro"
                    role="alert"
                    style={{ color: 'var(--critic)', letterSpacing: '0.08em' }}
                  >
                    {submitError.message}
                  </span>
                )}
                {showPreviewErrorInline && (
                  <span
                    className="micro"
                    role="alert"
                    style={{ color: 'var(--critic)', letterSpacing: '0.08em' }}
                  >
                    {previewError.message}
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Recent / example questions */}
          <div style={{ marginTop: 48 }}>
            <div className="micro" style={{ marginBottom: 14 }}>
              Or start from a recent question
            </div>
            {/* TODO: replace static examples with follow-ups from history. */}
            <div className="grid grid-cols-2" style={{ borderTop: '1px solid var(--line-soft)' }}>
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleExampleClick(q)}
                  className="flex items-start gap-3.5 text-left transition-colors hover:bg-bg-2"
                  style={{
                    padding: '18px 20px 18px 0',
                    borderBottom: '1px solid var(--line-soft)',
                    borderRight: i % 2 === 0 ? '1px solid var(--line-soft)' : 'none',
                    paddingLeft: i % 2 === 1 ? 24 : 0,
                  }}
                >
                  <span
                    className="font-mono"
                    style={{ fontSize: 11, color: 'var(--muted)', paddingTop: 3 }}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span
                    className="serif"
                    style={{ fontSize: 16, lineHeight: 1.4, color: 'var(--fg-2)' }}
                  >
                    {q}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </main>

        {/* Library sidebar */}
        <aside
          className="overflow-auto"
          style={{
            borderLeft: '1px solid var(--line)',
            padding: '24px 20px',
            background: 'var(--bg-2)',
          }}
        >
          <div className="flex items-baseline justify-between" style={{ marginBottom: 16 }}>
            <span className="micro">Library — recent</span>
            <Link
              to="/history"
              className="font-mono"
              style={{
                fontSize: 10,
                color: 'var(--muted)',
                letterSpacing: '0.08em',
                textDecoration: 'none',
              }}
            >
              ALL →
            </Link>
          </div>

          {history.data && history.data.length > 0 ? (
            <div className="flex flex-col">
              {history.data.map((job, i) => (
                <Link
                  key={job.id}
                  to="/research/$jobId"
                  params={{ jobId: job.id }}
                  className="block transition-colors hover:bg-bg-3"
                  style={{
                    padding: '14px 0',
                    borderBottom:
                      i < (history.data?.length ?? 0) - 1 ? '1px solid var(--line-soft)' : 'none',
                    textDecoration: 'none',
                    color: 'inherit',
                  }}
                >
                  <div
                    className="serif"
                    style={{
                      fontSize: 14,
                      lineHeight: 1.3,
                      marginBottom: 8,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {job.topic}
                  </div>
                  <div className="flex items-center justify-between">
                    <ConfidenceBar value={job.progress ?? 0} />
                    <span className="font-mono" style={{ fontSize: 10, color: 'var(--muted)' }}>
                      {job.created_at
                        ? new Date(job.created_at).toLocaleDateString('en-GB', {
                            day: '2-digit',
                            month: 'short',
                          })
                        : ''}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div
              className="serif"
              style={{
                marginTop: 8,
                padding: 16,
                background: 'var(--bg)',
                border: '1px solid var(--line-soft)',
                fontSize: 13,
                lineHeight: 1.5,
                color: 'var(--fg-3)',
                fontWeight: 300,
                fontStyle: 'italic',
              }}
            >
              No briefs yet. Your library fills as Scout, Scribe and Critic finish their first run.
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
