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
  'What does the latest evidence say about microplastics in human placenta?',
  'Trace the regulatory history of GLP-1 agonists for non-diabetic use, 2020 to today.',
  "Who actually owns Romania's offshore Black Sea gas, and how has it shifted since 2022?",
  'Compare battery recycling economics: EU vs. China vs. US, post-IRA.',
]

const DEPTH_LABELS: Record<string, string> = {
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
    <div className="flex flex-col h-screen overflow-hidden bg-bg text-fg">
      {/* Top bar */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-line flex-shrink-0">
        <div className="flex items-center gap-7">
          <div className="flex items-center gap-2.5">
            <SynapseMark size={28} />
            <span className="serif text-[17px] font-medium">Synapse</span>
          </div>
          <nav className="flex gap-[18px]">
            <span className="label">New brief</span>
            <Link
              to="/history"
              className="label text-muted"
              style={{ textDecoration: 'none', color: 'var(--muted)' }}
            >
              Library
            </Link>
            <span className="label text-muted">Sources</span>
            <span className="label text-muted">Settings</span>
          </nav>
        </div>
        <div className="flex items-center gap-3.5">
          <span className="micro">
            {/* TODO: replace hard-coded 50 with a backend setting when available. */}
            {briefCount} / 50 briefs this month
          </span>
          <div
            className="w-7 h-7 rounded-full bg-bg-3 flex items-center justify-center serif text-[13px]"
            aria-label="user avatar"
          >
            {me ? getInitials(me.email) : ''}
          </div>
        </div>
      </header>

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-[1fr_280px] overflow-hidden">
        {/* Left column */}
        <main className="px-20 py-[60px] flex flex-col justify-center overflow-auto">
          <div className="micro mb-4">{formatNow()}</div>
          <h1 className="serif text-[64px] leading-none tracking-[-0.03em] font-light">
            What would you like
            <br />
            to <em className="italic">understand</em>?
          </h1>

          {/* Topic card */}
          <div className="mt-12 border border-fg p-6 bg-bg-2">
            <div className="label mb-3 text-muted">Topic</div>
            <textarea
              {...topicRest}
              ref={(el) => {
                topicRef(el)
                textareaRef.current = el
              }}
              placeholder="Type your research topic here..."
              rows={1}
              className="w-full bg-transparent serif text-[28px] leading-[1.3] font-light text-fg placeholder:text-muted outline-none resize-none overflow-hidden"
              style={{ minHeight: 80 }}
            />

            {/* Pills row */}
            <div className="flex flex-wrap items-center gap-3 mt-6 pt-5 border-t border-line">
              <Pill
                label="Depth"
                value={
                  <select
                    value={depthValue}
                    onChange={(e) => setValue('depth', e.target.value as FormData['depth'])}
                    className="bg-transparent font-sans text-[12px] cursor-pointer outline-none"
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

              {/* Display-only pills matching the figma layout; not yet wired to backend. */}
              <Pill label="Recency" value="Last 12 months" disabled />
              <Pill label="Sources" value="Web + Crunchbase + Pitchbook" disabled />
              <Pill label="Min / question" value="≥ 5 sources" disabled />
              <Pill label="Length" value="~ 2,500 words" disabled />
              <Pill label="Deliver as" value="PDF + Markdown" disabled />

              <div className="ml-auto flex gap-2">
                <Button variant="ghost" size="sm" disabled>
                  + Constraint
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={previewResearch.isPending}
                  onClick={handleSubmit(onPreview)}
                >
                  {previewResearch.isPending ? 'Generating plan...' : 'Preview plan →'}
                </Button>
              </div>
            </div>

            {/* Submit */}
            <div className="mt-6 flex items-center gap-4">
              <Button
                type="button"
                onClick={handleSubmit(onSubmit)}
                disabled={startResearch.isPending}
              >
                Start brief →
              </Button>
              {errors.topic && (
                <span className="text-[12px] text-critic" role="alert">
                  {errors.topic.message}
                </span>
              )}
              {showErrorInline && (
                <span className="text-[12px] text-critic" role="alert">
                  {submitError.message}
                </span>
              )}
              {showPreviewErrorInline && (
                <span className="text-[12px] text-critic" role="alert">
                  {previewError.message}
                </span>
              )}
            </div>
          </div>

          {/* Recent questions */}
          <div className="mt-12">
            <div className="micro mb-3.5">Or start from a recent question</div>
            {/* TODO: replace static examples with follow-ups from history. */}
            <div className="grid grid-cols-2 border-t border-line-soft">
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleExampleClick(q)}
                  className="flex items-start gap-3.5 py-[18px] text-left border-b border-line-soft hover:bg-bg-2 transition-colors"
                  style={{
                    borderRight: i % 2 === 0 ? '1px solid var(--line-soft)' : 'none',
                    paddingLeft: i % 2 === 1 ? '24px' : '0',
                    paddingRight: i % 2 === 0 ? '20px' : '0',
                  }}
                >
                  <span className="font-mono text-[11px] text-muted pt-[3px]">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="serif text-[16px] leading-[1.4] text-fg-2">{q}</span>
                </button>
              ))}
            </div>
          </div>
        </main>

        {/* Library sidebar */}
        <aside className="border-l border-line p-6 bg-bg-2 overflow-auto">
          <div className="micro mb-4">Library — recent</div>
          {history.data && history.data.length > 0 ? (
            <div className="flex flex-col">
              {history.data.map((job, i) => (
                <div
                  key={job.id}
                  className="py-3.5"
                  style={{
                    borderBottom:
                      i < (history.data?.length ?? 0) - 1 ? '1px solid var(--line-soft)' : 'none',
                  }}
                >
                  <div className="serif text-[14px] leading-[1.3] mb-2">{job.topic}</div>
                  <div className="flex items-center justify-between">
                    <ConfidenceBar value={job.progress ?? 0} />
                    <span className="font-mono text-[10px] text-muted">
                      {job.created_at
                        ? new Date(job.created_at).toLocaleDateString('en-GB', {
                            day: '2-digit',
                            month: 'short',
                          })
                        : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[13px] text-muted bg-bg p-3 border border-line-soft">
              No briefs yet — your library is empty.
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
