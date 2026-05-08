import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { z } from 'zod'

import { Button } from '../components/ui/Button'
import { useLogin } from '../hooks/useAuth'

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

type LoginFormData = z.infer<typeof loginSchema>

export default function LoginPage() {
  const navigate = useNavigate()
  const { redirect } = useSearch({ from: '/login' })
  const login = useLogin()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null)
    try {
      await login.mutateAsync({ email: data.email, password: data.password })
      await navigate({ to: redirect ?? '/research/new' })
    } catch (err) {
      if (err instanceof Error) {
        setServerError(err.message)
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4">
      <div className="w-full max-w-[400px]">
        <h1 className="serif text-[42px] font-normal tracking-tight mb-10">Sign in</h1>

        {serverError && (
          <p role="alert" className="text-critic text-sm mb-6">
            {serverError}
          </p>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
          <div>
            <label htmlFor="email" className="label block mb-2">
              Email
            </label>
            <input
              id="email"
              type="email"
              {...register('email')}
              className="w-full bg-transparent border-b border-line py-2 text-fg outline-none focus:border-fg transition-colors"
            />
            {errors.email && (
              <p role="alert" className="text-critic text-xs mt-1">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="label block mb-2">
              Password
            </label>
            <input
              id="password"
              type="password"
              {...register('password')}
              className="w-full bg-transparent border-b border-line py-2 text-fg outline-none focus:border-fg transition-colors"
            />
            {errors.password && (
              <p role="alert" className="text-critic text-xs mt-1">
                {errors.password.message}
              </p>
            )}
          </div>

          <Button type="submit" disabled={login.isPending} className="mt-2">
            {login.isPending ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>

        <p className="text-sm text-fg-2 mt-6">
          Don&apos;t have an account?{' '}
          <Link
            to="/register"
            search={{ redirect }}
            className="text-fg underline underline-offset-4"
          >
            Register →
          </Link>
        </p>
      </div>
    </div>
  )
}
