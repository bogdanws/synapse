import { useForm, type SubmitHandler } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { z } from 'zod'

import { AppNavbar, SynapseBrandLink } from '../components/AppNavbar'
import { Button } from '../components/ui/Button'
import { useReport } from '../hooks/useReport'
import { useStartFollowUp } from '../hooks/useStartFollowUp'
import { ApiError } from '../services/api'

const formSchema = z.object({
  question: z
    .string()
    .trim()
    .min(3, 'Ask a question of at least 3 characters')
    .max(500, 'Keep the question under 500 characters'),
})

type FormData = z.infer<typeof formSchema>

export default function FollowUpPage() {
  const { jobId } = useParams({ from: '/research/$jobId/follow-up' })
  const navigate = useNavigate()
  const { data, isLoading } = useReport(jobId)
  const followUp = useStartFollowUp(jobId)

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(formSchema), defaultValues: { question: '' } })

  const onSubmit: SubmitHandler<FormData> = ({ question }) => {
    // Navigate from the mutation's success callback rather than awaiting
    // `mutateAsync`, so a rejected request surfaces through `followUp.error`
    // instead of becoming an unhandled promise rejection.
    followUp.mutate(question, {
      onSuccess: (child) => {
        navigate({ to: '/research/$jobId', params: { jobId: child.id } })
      },
    })
  }

  const suggestions = data?.report.follow_ups ?? []
  const parentTitle = data?.report.title
  const submitError =
    followUp.error instanceof ApiError ? followUp.error.message : (followUp.error?.message ?? null)

  return (
    <div
      className="min-h-screen flex flex-col overflow-hidden relative"
      style={{ background: 'var(--bg-2)', color: 'var(--fg)' }}
    >
      {/* Paper grid */}
      <svg width="100%" height="100%" className="absolute inset-0 pointer-events-none" aria-hidden>
        <defs>
          <pattern id="follow-up-grid" width="44" height="44" patternUnits="userSpaceOnUse">
            <path d="M 44 0 L 0 0 0 44" fill="none" stroke="var(--line-soft)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#follow-up-grid)" />
      </svg>

      {/* Breadcrumb chrome — keeps the path back to the originating report. */}
      <AppNavbar
        variant="app"
        className="flex items-center gap-2.5 px-4 sm:px-8 shrink-0 relative z-10"
      >
        <SynapseBrandLink
          className="flex items-center gap-2.5"
          markSize={22}
          labelClassName="serif"
          labelStyle={{ fontSize: 17, fontWeight: 500 }}
        />
        <span className="w-px h-4 shrink-0" style={{ background: 'var(--line)' }} aria-hidden />
        <Link
          to="/research/$jobId/report"
          params={{ jobId }}
          className="micro"
          style={{ color: 'var(--muted)', textDecoration: 'none' }}
        >
          Report
        </Link>
        <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>
          ›
        </span>
        <span className="label">Follow-up</span>
      </AppNavbar>

      {/* Centered composition card */}
      <div className="flex-1 flex items-center justify-center px-4 py-10 relative z-10">
        <div
          className="w-full max-w-[680px]"
          style={{ background: 'var(--bg)', border: '1px solid var(--fg)' }}
        >
          {/* Stamped header */}
          <div
            className="flex justify-between items-center px-6 py-3.5"
            style={{ borderBottom: '1px solid var(--fg)' }}
          >
            <span className="micro">Follow-up brief</span>
            <div className="flex gap-1.5">
              {(['scout', 'scribe', 'critic'] as const).map((a) => (
                <span
                  key={a}
                  className="w-2 h-2 rounded-full"
                  style={{ background: `var(--${a})` }}
                />
              ))}
            </div>
          </div>

          <div className="px-6 sm:px-12 pt-10 pb-9">
            <p className="micro" style={{ marginBottom: 10 }}>
              Continuing from
            </p>
            <h1
              className="serif font-light m-0"
              style={{
                fontSize: 'clamp(28px, 4vw, 40px)',
                lineHeight: 1.02,
                letterSpacing: '-0.025em',
                color: 'var(--fg)',
                textWrap: 'balance',
              }}
            >
              {isLoading ? 'Loading report…' : (parentTitle ?? 'this report')}
            </h1>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-9 flex flex-col gap-5">
              <div className="flex flex-col gap-2.5">
                <label
                  className="label"
                  htmlFor="follow-up-question"
                  style={{ color: 'var(--muted)' }}
                >
                  Your question
                </label>
                <textarea
                  id="follow-up-question"
                  {...register('question')}
                  rows={4}
                  placeholder="Ask something this report raised but didn't fully answer…"
                  className="serif w-full resize-y outline-none transition-colors focus:border-fg placeholder:text-fg-3"
                  style={{
                    padding: '16px 18px',
                    fontSize: 19,
                    fontWeight: 300,
                    lineHeight: 1.45,
                    letterSpacing: '-0.005em',
                    background: 'var(--bg-2)',
                    color: 'var(--fg)',
                    border: '1px solid var(--line)',
                  }}
                />
                {errors.question && (
                  <p className="micro" style={{ color: 'var(--critic)' }} role="alert">
                    {errors.question.message}
                  </p>
                )}
              </div>

              {suggestions.length > 0 && (
                <div className="flex flex-col gap-2.5">
                  <p className="micro">Suggested by the report</p>
                  <div style={{ borderTop: '1px solid var(--line-soft)' }}>
                    {suggestions.map((q, i) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() =>
                          setValue('question', q, { shouldValidate: true, shouldDirty: true })
                        }
                        className="flex items-start gap-3.5 w-full text-left transition-colors hover:bg-bg-2 py-3.5 pr-1"
                        style={{ borderBottom: '1px solid var(--line-soft)' }}
                      >
                        <span
                          className="font-mono shrink-0"
                          style={{
                            fontSize: '0.6875rem',
                            color: 'var(--muted)',
                            paddingTop: '0.25rem',
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

              {submitError && (
                <p className="micro" style={{ color: 'var(--critic)' }} role="alert">
                  {submitError}
                </p>
              )}

              <div className="flex items-center gap-5" style={{ marginTop: 2 }}>
                <Button type="submit" disabled={followUp.isPending}>
                  {followUp.isPending ? 'Launching…' : 'Launch follow-up →'}
                </Button>
                <Link
                  to="/research/$jobId/report"
                  params={{ jobId }}
                  className="label"
                  style={{
                    color: 'var(--muted)',
                    textDecoration: 'underline',
                    textUnderlineOffset: 4,
                  }}
                >
                  ← Back to report
                </Link>
              </div>
            </form>
          </div>

          {/* Footer strip */}
          <div
            className="px-6 py-4"
            style={{ borderTop: '1px solid var(--line)', background: 'var(--bg-2)' }}
          >
            <span className="serif" style={{ fontSize: 13, color: 'var(--fg-2)', fontWeight: 300 }}>
              The follow-up will reuse this report&apos;s sources and inherit its models.
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
