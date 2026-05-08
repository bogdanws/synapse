import { useQuery } from '@tanstack/react-query'

import { usersCurrentUserApiAuthUsersMeGet } from '../types/api'
import type { UserRead } from '../types/api'

// Returns the authenticated user, or undefined when unauthenticated.
export function useMe(): UserRead | undefined {
  const { data } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: async (): Promise<UserRead | null> => {
      const result = await usersCurrentUserApiAuthUsersMeGet()
      return result.data ?? null
    },
    retry: false,
  })
  return data ?? undefined
}
