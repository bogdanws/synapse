import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { z } from 'zod'

import { AuthNavbar } from '../components/AppNavbar'
import { Button } from '../components/ui/Button'
import { useLogin, useRegister } from '../hooks/useAuth'

const registerSchema = z
  .object({
    firstName: z.string().min(1, 'First name is required').max(100),
    lastName: z.string().min(1, 'Last name is required').max(100),
    email: z.string().email('Invalid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  })

type RegisterFormData = z.infer<typeof registerSchema>

function Field({
  id,
  label,
  type = 'text',
  error,
  registration,
}: {
  id: string
  label: string
  type?: string
  error?: string
  registration: ReturnType<ReturnType<typeof useForm<RegisterFormData>>['register']>
}) {
  return (
    <div>
      <div className="mb-2">
        <label htmlFor={id} className="label" style={{ color: 'var(--muted)' }}>
          {label}
        </label>
      </div>
      <input
        id={id}
        type={type}
        {...registration}
        className="w-full bg-transparent border-b border-fg py-2.5 text-fg text-[17px] tracking-[-0.01em] outline-none focus:border-fg transition-colors placeholder:text-fg-3"
        style={{ fontFamily: 'var(--sans)' }}
      />
      {error && (
        <p role="alert" className="micro mt-2" style={{ color: 'var(--critic)' }}>
          {error}
        </p>
      )}
    </div>
  )
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const { email, redirect } = useSearch({ from: '/register' })
  const registerMutation = useRegister()
  const loginMutation = useLogin()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    defaultValues: { email: email ?? '' },
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormData) => {
    setServerError(null)
    try {
      await registerMutation.mutateAsync({
        email: data.email,
        password: data.password,
        first_name: data.firstName,
        last_name: data.lastName,
      })
      await loginMutation.mutateAsync({
        email: data.email,
        password: data.password,
      })
      await navigate({ to: redirect ?? '/research/new' })
    } catch (err) {
      if (err instanceof Error) {
        setServerError(err.message)
      }
    }
  }

  return (
    <div
      className="min-h-screen flex flex-col overflow-hidden relative"
      style={{ background: 'var(--bg-2)', color: 'var(--fg)' }}
    >
      {/* Paper grid */}
      <svg width="100%" height="100%" className="absolute inset-0 pointer-events-none" aria-hidden>
        <defs>
          <pattern id="reg-grid" width="44" height="44" patternUnits="userSpaceOnUse">
            <path d="M 44 0 L 0 0 0 44" fill="none" stroke="var(--line-soft)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#reg-grid)" />
      </svg>

      {/* Masthead */}
      <AuthNavbar tagline="Private beta · sign up" />

      {/* Centered card */}
      <div className="flex-1 flex items-center justify-center px-4 py-10 relative z-10">
        <div
          className="w-full max-w-[540px]"
          style={{ background: 'var(--bg)', border: '1px solid var(--fg)' }}
        >
          {/* Stamped header */}
          <div
            className="flex justify-between items-center px-6 py-3.5"
            style={{ borderBottom: '1px solid var(--fg)' }}
          >
            <span className="micro">New account</span>
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

          <div className="px-6 sm:px-14 pt-12 pb-10">
            <h1
              className="serif text-center font-normal m-0"
              style={{
                fontSize: 'clamp(36px, 6vw, 56px)',
                lineHeight: 0.95,
                letterSpacing: '-0.035em',
              }}
            >
              Create account.
            </h1>
            <p
              className="serif text-center mt-3.5 mb-0 font-light italic"
              style={{ fontSize: 15, lineHeight: 1.4, color: 'var(--fg-2)' }}
            >
              Scout, Scribe and Critic are ready when you are.
            </p>

            {serverError && (
              <p role="alert" className="micro mt-6 text-center" style={{ color: 'var(--critic)' }}>
                {serverError}
              </p>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="mt-9 flex flex-col gap-6" noValidate>
              {/* Name row — 2 columns on sm+, stacked on mobile */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-x-5">
                <Field
                  id="firstName"
                  label="First name"
                  error={errors.firstName?.message}
                  registration={register('firstName')}
                />
                <Field
                  id="lastName"
                  label="Last name"
                  error={errors.lastName?.message}
                  registration={register('lastName')}
                />
              </div>

              <Field
                id="email"
                label="Email"
                type="email"
                error={errors.email?.message}
                registration={register('email')}
              />
              <Field
                id="password"
                label="Password"
                type="password"
                error={errors.password?.message}
                registration={register('password')}
              />
              <Field
                id="confirmPassword"
                label="Confirm password"
                type="password"
                error={errors.confirmPassword?.message}
                registration={register('confirmPassword')}
              />

              <Button
                type="submit"
                disabled={registerMutation.isPending || loginMutation.isPending}
                className="mt-1 w-full justify-center"
              >
                {registerMutation.isPending || loginMutation.isPending
                  ? 'Creating account…'
                  : 'Create account →'}
              </Button>
            </form>
          </div>

          {/* Footer strip */}
          <div
            className="flex justify-between items-center px-6 py-4"
            style={{ borderTop: '1px solid var(--line)', background: 'var(--bg-2)' }}
          >
            <span className="serif" style={{ fontSize: 13, color: 'var(--fg-2)', fontWeight: 300 }}>
              Already have an account?{' '}
              <Link
                to="/login"
                search={{ redirect }}
                style={{ color: 'var(--fg)', textDecoration: 'underline', textUnderlineOffset: 3 }}
              >
                Sign in →
              </Link>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
