import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { z } from 'zod'

import { Button } from '../components/ui/Button'
import { useLogin, useRegister } from '../hooks/useAuth'

const registerSchema = z
  .object({
    email: z.string().email('Invalid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  })

type RegisterFormData = z.infer<typeof registerSchema>

export default function RegisterPage() {
  const navigate = useNavigate()
  const { redirect } = useSearch({ from: '/register' })
  const registerMutation = useRegister()
  const loginMutation = useLogin()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  })

  const onSubmit = async (data: RegisterFormData) => {
    setServerError(null)
    try {
      await registerMutation.mutateAsync({
        email: data.email,
        password: data.password,
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
    <div className="min-h-screen flex items-center justify-center bg-bg px-4">
      <div className="w-full max-w-[400px]">
        <h1 className="serif text-[42px] font-normal tracking-tight mb-10">Create account</h1>

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

          <div>
            <label htmlFor="confirmPassword" className="label block mb-2">
              Confirm password
            </label>
            <input
              id="confirmPassword"
              type="password"
              {...register('confirmPassword')}
              className="w-full bg-transparent border-b border-line py-2 text-fg outline-none focus:border-fg transition-colors"
            />
            {errors.confirmPassword && (
              <p role="alert" className="text-critic text-xs mt-1">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          <Button
            type="submit"
            disabled={registerMutation.isPending || loginMutation.isPending}
            className="mt-2"
          >
            {registerMutation.isPending || loginMutation.isPending
              ? 'Creating account...'
              : 'Create account'}
          </Button>
        </form>

        <p className="text-sm text-fg-2 mt-6">
          Already have an account?{' '}
          <Link to="/login" search={{ redirect }} className="text-fg underline underline-offset-4">
            Sign in →
          </Link>
        </p>
      </div>
    </div>
  )
}
