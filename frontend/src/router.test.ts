import { describe, it, expect, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { redirect } from '@tanstack/react-router'

import { requireAuth } from './router'

vi.mock('./types/api', () => ({
  usersCurrentUserApiAuthUsersMeGet: vi.fn(),
}))

import { usersCurrentUserApiAuthUsersMeGet } from './types/api'

describe('requireAuth', () => {
  it('throws redirect when the user is not authenticated', async () => {
    const queryClient = new QueryClient()
    vi.mocked(usersCurrentUserApiAuthUsersMeGet).mockResolvedValue({
      data: undefined,
      response: { ok: false, status: 401 } as Response,
      request: {} as Request,
    } as never)

    await expect(requireAuth(queryClient, '/research/new')).rejects.toBeDefined()

    // Verify the thrown value is a TanStack Router redirect
    try {
      await requireAuth(queryClient, '/research/new')
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(redirect({ to: '/login' }).constructor)
    }
  })

  it('returns the user when authenticated', async () => {
    const queryClient = new QueryClient()
    vi.mocked(usersCurrentUserApiAuthUsersMeGet).mockResolvedValue({
      data: { id: 'u1', email: 'test@example.com' },
      response: { ok: true, status: 200 } as Response,
      request: {} as Request,
    } as never)

    const user = await requireAuth(queryClient, '/research/new')
    expect(user).toEqual({ id: 'u1', email: 'test@example.com' })
  })
})
