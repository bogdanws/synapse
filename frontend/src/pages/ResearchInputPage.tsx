import { useRef, useEffect, useCallback } from 'react'
import { useForm, type SubmitHandler } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { z } from 'zod'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'
import { Button } from '../components/ui/Button'
import { Select, type SelectOption } from '../components/ui/Select'
import { AGENTS, AGENT_ORDER, type Agent } from '../components/ui/Agent'
import { AgentDot } from '../components/ui/AgentDot'
import { useMe } from '../hooks/useMe'
import { useAgentModels } from '../hooks/useAgentModels'
import { usePreviewResearch } from '../hooks/usePreviewResearch'
import { useResearchHistory } from '../hooks/useResearchHistory'
import { useStartResearch } from '../hooks/useStartResearch'
import { ApiError } from '../services/api'
import { ALLOWED_MODELS } from '../constants/models'
import type { JobStatus, JobSummary } from '../types/api'

const allowedModelIds: string[] = ALLOWED_MODELS.map((m) => m.id)

// How many briefs the "recent" rail shows before deferring to the full Library.
const RECENT_LIMIT = 6

// Each status maps to the agent whose colour represents that stage, plus whether
// the job is still running (terminal states get a static dot, live ones pulse).
const RECENT_STATUS: Record<JobStatus, { agent: Agent; label: string; active: boolean }> = {
  completed: { agent: 'scout', label: 'completed', active: false },
  failed: { agent: 'critic', label: 'failed', active: false },
  pending: { agent: 'scribe', label: 'pending', active: true },
  scouting: { agent: 'scribe', label: 'scouting', active: true },
  synthesizing: { agent: 'scribe', label: 'synthesizing', active: true },
  critiquing: { agent: 'scribe', label: 'critiquing', active: true },
}

function formatRecentDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
}

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

// How many recommended follow-ups the "start from a recent question" grid shows.
const RECENT_QUESTION_LIMIT = 4

/** One follow-up per completed report per pass (newest report first), then a second
 *  from each, until `limit` or suggestions are exhausted. Skips duplicate strings. */
function pickRoundRobinFollowUps(
  jobs: Pick<JobSummary, 'status' | 'follow_ups'>[],
  limit: number,
): string[] {
  const lists = jobs
    .filter((job) => job.status === 'completed')
    .map((job) => job.follow_ups ?? [])
    .filter((followUps) => followUps.length > 0)

  const picked: string[] = []
  const seen = new Set<string>()
  let round = 0

  while (picked.length < limit) {
    let addedThisRound = false
    for (const followUps of lists) {
      if (round >= followUps.length) continue
      const question = followUps[round]
      if (seen.has(question)) continue
      seen.add(question)
      picked.push(question)
      addedThisRound = true
      if (picked.length >= limit) break
    }
    if (!addedThisRound) break
    round += 1
  }

  return picked
}

const DEPTH_OPTIONS: ReadonlyArray<SelectOption<FormData['depth']>> = [
  { value: 'shallow', label: 'Shallow', description: 'Quick scan' },
  { value: 'standard', label: 'Standard', description: 'Balanced run' },
  { value: 'deep', label: 'Deep', description: 'Exhaustive sweep' },
]

const MODEL_OPTIONS: ReadonlyArray<SelectOption> = ALLOWED_MODELS.map((m) => ({
  value: m.id,
  label: m.label,
  description: m.id,
}))

/* Shared trigger styling: a pill-shaped button where the full surface — agent dot, label,
 * value text and caret — is the click target. Border lights up on hover, focus, and while
 * the popup is open so the affordance covers the whole shape rather than just the value text. */
const PILL_TRIGGER_CLASS =
  'border border-line px-3 py-1.5 gap-1.5 transition-colors duration-150 ' +
  'hover:border-fg focus-visible:border-fg data-[popup-open]:border-fg'

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
  // The history hook is paginated (useInfiniteQuery); the "recent" sidebar only needs a flat list.
  const historyItems = history.data?.pages.flatMap((p) => p.items) ?? []
  const recentItems = historyItems.slice(0, RECENT_LIMIT)
  const recentQuestions = pickRoundRobinFollowUps(historyItems, RECENT_QUESTION_LIMIT)
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

  const briefCount = historyItems.length

  const submitError = startResearch.error
  const showErrorInline =
    submitError instanceof ApiError && (submitError.status === 422 || submitError.status === 429)

  const previewError = previewResearch.error
  const showPreviewErrorInline =
    previewError instanceof ApiError && (previewError.status === 422 || previewError.status === 429)

  const { ref: topicRef, ...topicRest } = register('topic')

  return (
    <div
      className="flex flex-col min-h-screen lg:h-screen lg:overflow-hidden"
      style={{ background: 'var(--bg)', color: 'var(--fg)' }}
    >
      {/* App chrome */}
      <AppNavbar
        variant="app"
        className="flex items-center justify-between gap-3 px-4 sm:px-6 lg:px-8"
      >
        <div className="flex items-center gap-4 sm:gap-7 min-w-0">
          <SynapseBrandLink
            className="flex items-center gap-2.5 shrink-0"
            labelClassName="serif"
            labelStyle={{ fontSize: '1.0625rem', fontWeight: 500, letterSpacing: '-0.01em' }}
          />
          <nav className="flex gap-3 sm:gap-5">
            <span className="label">New brief</span>
            <Link
              to="/history"
              className="label"
              style={{ textDecoration: 'none', color: 'var(--muted)' }}
            >
              Library
            </Link>
            <span className="label hidden md:inline" style={{ color: 'var(--muted)' }}>
              Sources
            </span>
            <span className="label hidden md:inline" style={{ color: 'var(--muted)' }}>
              Settings
            </span>
          </nav>
        </div>
        <div className="flex items-center gap-2 sm:gap-3.5 shrink-0">
          <span className="micro hidden sm:inline">
            {/* TODO: replace hard-coded 50 with a backend setting when available. */}
            {briefCount} / 50 briefs this month
          </span>
          <span className="micro sm:hidden" aria-label="briefs this month">
            {briefCount}/50
          </span>
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center serif"
            style={{ background: 'var(--bg-3)', fontSize: '0.8125rem' }}
            aria-label="user avatar"
          >
            {me ? getInitials(me.email) : ''}
          </div>
        </div>
      </AppNavbar>

      {/* Main */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_20rem] lg:overflow-hidden">
        {/* Composition column */}
        <main className="flex flex-col px-5 py-10 sm:px-10 sm:py-12 lg:px-20 lg:py-16 lg:overflow-auto">
          <div className="micro" style={{ marginBottom: '1rem' }}>
            {formatNow()}
          </div>
          <h1
            className="serif m-0 text-4xl sm:text-5xl lg:text-6xl"
            style={{
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
            className="mt-8 sm:mt-10 lg:mt-12 p-4 sm:p-6"
            style={{
              border: '1px solid var(--fg)',
              background: 'var(--bg-2)',
            }}
          >
            <div className="label" style={{ marginBottom: '0.75rem', color: 'var(--muted)' }}>
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
              className="serif w-full bg-transparent outline-none resize-none overflow-hidden text-xl sm:text-2xl lg:text-3xl"
              style={{
                lineHeight: 1.3,
                fontWeight: 300,
                color: 'var(--fg)',
                minHeight: '5rem',
                letterSpacing: '-0.005em',
              }}
            />

            {/* Controls row — depth + three agent model selectors, actions on the right. */}
            <div
              className="flex flex-wrap items-center gap-3"
              style={{
                marginTop: '1.5rem',
                paddingTop: '1.25rem',
                borderTop: '1px solid var(--line)',
              }}
            >
              <Select
                value={depthValue}
                onValueChange={(v) => setValue('depth', v)}
                options={DEPTH_OPTIONS}
                ariaLabel="Research depth"
                triggerClassName={PILL_TRIGGER_CLASS}
                renderTrigger={(opt) => (
                  <span className="flex flex-col items-start min-w-0 mr-1.5">
                    <span className="micro leading-none">Depth</span>
                    <span className="font-sans text-sm leading-tight mt-0.5 text-fg">
                      {opt?.label ?? '—'}
                    </span>
                  </span>
                )}
              />

              {AGENT_ORDER.map((agent) => (
                <Select
                  key={agent}
                  value={models[agent]}
                  onValueChange={(v) => handleModelChange(agent, v)}
                  options={MODEL_OPTIONS}
                  ariaLabel={`${AGENTS[agent].name} model`}
                  popupClassName="min-w-64"
                  triggerClassName={PILL_TRIGGER_CLASS}
                  renderTrigger={(opt) => (
                    <>
                      <AgentDot agent={agent} size={18} className="mr-1" />
                      <span className="flex flex-col items-start min-w-0 mr-1.5">
                        <span className="micro leading-none">{AGENTS[agent].name}</span>
                        <span className="font-sans text-sm leading-tight mt-0.5 text-fg truncate max-w-36">
                          {opt?.label ?? '—'}
                        </span>
                      </span>
                    </>
                  )}
                />
              ))}

              <div className="flex w-full sm:w-auto sm:ml-auto items-center gap-2">
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
              <div className="flex flex-col gap-1" style={{ marginTop: '0.875rem' }}>
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

          {/* Recommended follow-ups from completed briefs. Hidden until at least
           * one finished report has suggestions, so a new account never sees an
           * empty grid. */}
          {recentQuestions.length > 0 && (
            <div className="mt-10 sm:mt-12">
              <div className="micro" style={{ marginBottom: '0.875rem' }}>
                Or start from a recent question
              </div>
              <div
                className="grid grid-cols-1 sm:grid-cols-2"
                style={{ borderTop: '1px solid var(--line-soft)' }}
              >
                {recentQuestions.map((q, i) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleExampleClick(q)}
                    className={`flex items-start gap-3.5 text-left transition-colors hover:bg-bg-2 py-5 pr-5 ${
                      i % 2 === 0
                        ? i + 1 < recentQuestions.length
                          ? 'sm:border-r'
                          : ''
                        : 'sm:pl-6'
                    }`}
                    style={{
                      borderBottom: '1px solid var(--line-soft)',
                      borderRightColor: 'var(--line-soft)',
                    }}
                  >
                    <span
                      className="font-mono"
                      style={{
                        fontSize: '0.6875rem',
                        color: 'var(--muted)',
                        paddingTop: '0.1875rem',
                      }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span
                      className="serif"
                      style={{ fontSize: '1rem', lineHeight: 1.4, color: 'var(--fg-2)' }}
                    >
                      {q}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </main>

        {/* Library sidebar — stacks below the composition column on small screens
         * so the brief composer always gets the full viewport width. The divider
         * switches from a top rule (stacked) to a left rule (side-by-side). */}
        <aside
          className="px-5 py-6 sm:px-6 border-t lg:border-t-0 lg:border-l border-line lg:overflow-auto"
          style={{ background: 'var(--bg-2)' }}
        >
          <div className="flex items-baseline justify-between" style={{ marginBottom: '1rem' }}>
            <span className="micro">Library — recent</span>
            <Link
              to="/history"
              className="font-mono"
              style={{
                fontSize: '0.625rem',
                color: 'var(--muted)',
                letterSpacing: '0.08em',
                textDecoration: 'none',
              }}
            >
              ALL →
            </Link>
          </div>

          {recentItems.length > 0 ? (
            <div className="flex flex-col">
              {recentItems.map((job, i) => (
                <RecentRow key={job.id} job={job} divider={i < recentItems.length - 1} />
              ))}
            </div>
          ) : (
            <div
              className="serif"
              style={{
                marginTop: '0.5rem',
                padding: '1rem',
                background: 'var(--bg)',
                border: '1px solid var(--line-soft)',
                fontSize: '0.8125rem',
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

// A single brief in the "recent" rail.
function RecentRow({ job, divider }: { job: JobSummary; divider: boolean }) {
  const status = RECENT_STATUS[job.status]
  const done = job.status === 'completed'

  return (
    <Link
      to={done ? '/research/$jobId/report' : '/research/$jobId'}
      params={{ jobId: job.id }}
      className="group block transition-colors hover:bg-bg-3"
      style={{
        padding: '0.875rem 0',
        borderBottom: divider ? '1px solid var(--line-soft)' : 'none',
        textDecoration: 'none',
        color: 'inherit',
        opacity: job.status === 'failed' ? 0.65 : 1,
      }}
    >
      <div
        className="serif"
        style={{
          fontSize: '0.875rem',
          lineHeight: 1.35,
          fontWeight: 300,
          marginBottom: '0.5rem',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {job.topic}
      </div>
      <div className="flex items-center justify-between gap-2">
        <span
          className="flex items-center gap-1.5 min-w-0"
          style={{ color: `var(--${status.agent})` }}
        >
          <span
            className={status.active ? 'pulse-dot' : ''}
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'currentColor',
              flexShrink: 0,
            }}
            aria-hidden
          />
          <span className="label" style={{ fontSize: '0.625rem', color: 'inherit' }}>
            {status.label}
          </span>
        </span>
        <span
          className="font-mono shrink-0"
          style={{ fontSize: '0.625rem', color: 'var(--muted)' }}
        >
          {formatRecentDate(job.created_at)}
        </span>
      </div>
    </Link>
  )
}
