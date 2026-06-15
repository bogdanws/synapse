import { describe, it, expect, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { redirect } from '@tanstack/react-router'

import { getSafeAuthRedirect, requireAuth } from './router'

vi.mock('./types/api', () => ({
  usersCurrentUserApiAuthUsersMeGet: vi.fn(),
}))

import { usersCurrentUserApiAuthUsersMeGet } from './types/api'

describe('getSafeAuthRedirect', () => {
  it('defaults to the research form when redirect is missing', () => {
    expect(getSafeAuthRedirect(undefined)).toBe('/research/new')
  })

  it('preserves in-app relative paths', () => {
    expect(getSafeAuthRedirect('/history')).toBe('/history')
  })

  it('blocks protocol-relative and off-site redirects', () => {
    expect(getSafeAuthRedirect('//evil.example')).toBe('/research/new')
    expect(getSafeAuthRedirect('https://evil.example')).toBe('/research/new')
  })
})

describe('requireAuth', () => {
  it('throws redirect with the original href when the user is not authenticated', async () => {
    const queryClient = new QueryClient()
    vi.mocked(usersCurrentUserApiAuthUsersMeGet).mockResolvedValue({
      data: undefined,
      response: { ok: false, status: 401 } as Response,
      request: {} as Request,
    } as never)

    await expect(requireAuth(queryClient, '/research/new')).rejects.toBeDefined()

    try {
      await requireAuth(queryClient, '/research/new')
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(redirect({ to: '/login' }).constructor)
      expect(err).toMatchObject({
        options: {
          to: '/login',
          search: { redirect: '/research/new' },
        },
      })
    }
  })

  it('returns the user when authenticated', async () => {
    const queryClient = new QueryClient()
    vi.mocked(usersCurrentUserApiAuthUsersMeGet).mockResolvedValue({
      data: { id: 'u1', email: 'test@example.com' },
      response: { ok: true, status: 200 } as Response,
      request: {} as Request,
    } as never)

    const user = await requireAuth(queryClient, '/history')
    expect(user).toEqual({ id: 'u1', email: 'test@example.com' })
  })
})
