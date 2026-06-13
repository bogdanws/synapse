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

  const onSubmit: SubmitHandler<FormData> = async ({ question }) => {
    const child = await followUp.mutateAsync(question)
    navigate({ to: '/research/$jobId', params: { jobId: child.id } })
  }

  const suggestions = data?.report.follow_ups ?? []
  const parentTitle = data?.report.title
  const submitError =
    followUp.error instanceof ApiError ? followUp.error.message : (followUp.error?.message ?? null)

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

      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '32px',
        }}
      >
        <form
          onSubmit={handleSubmit(onSubmit)}
          style={{ width: '100%', maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 20 }}
        >
          <div>
            <p className="micro" style={{ marginBottom: 8 }}>
              Follow up on
            </p>
            <h1
              className="serif"
              style={{
                fontSize: 30,
                fontWeight: 300,
                letterSpacing: '-0.02em',
                margin: 0,
                color: 'var(--fg)',
                textWrap: 'balance',
              }}
            >
              {isLoading ? 'Loading report…' : (parentTitle ?? 'this report')}
            </h1>
          </div>

          <label className="label" htmlFor="follow-up-question">
            Your question
          </label>
          <textarea
            id="follow-up-question"
            {...register('question')}
            rows={4}
            placeholder="Ask something this report raised but didn't fully answer…"
            className="serif"
            style={{
              width: '100%',
              resize: 'vertical',
              padding: '14px 16px',
              fontSize: 18,
              lineHeight: 1.5,
              background: 'var(--bg-2)',
              color: 'var(--fg)',
              border: '1px solid var(--line)',
              borderRadius: 2,
            }}
          />
          {errors.question && (
            <p className="micro" style={{ color: 'var(--critic)' }} role="alert">
              {errors.question.message}
            </p>
          )}

          {suggestions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <p className="micro" style={{ color: 'var(--muted)' }}>
                Suggested by the report
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {suggestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() =>
                      setValue('question', q, { shouldValidate: true, shouldDirty: true })
                    }
                    className="micro"
                    style={{
                      textAlign: 'left',
                      padding: '6px 10px',
                      background: 'transparent',
                      color: 'var(--fg-2)',
                      border: '1px solid var(--line)',
                      borderRadius: 999,
                      cursor: 'pointer',
                    }}
                  >
                    {q}
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

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Button type="submit" disabled={followUp.isPending}>
              {followUp.isPending ? 'Launching…' : 'Launch follow-up →'}
            </Button>
            <Link
              to="/research/$jobId/report"
              params={{ jobId }}
              className="label"
              style={{ color: 'var(--muted)', textDecoration: 'underline', textUnderlineOffset: 4 }}
            >
              ← Back to report
            </Link>
          </div>
          <p className="micro" style={{ color: 'var(--muted)' }}>
            Reuses this report&apos;s sources and inherits its models, language, and depth.
          </p>
        </form>
      </div>
    </div>
  )
}
