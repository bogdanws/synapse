import {
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'
import { z } from 'zod'
import type { QueryClient } from '@tanstack/react-query'

import { usersCurrentUserApiAuthUsersMeGet } from './types/api'
import type { UserRead } from './types/api'

import JobProgressPage from './pages/JobProgressPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ResearchInputPage from './pages/ResearchInputPage'

const authSearchSchema = z.object({
  redirect: z.string().optional(),
})

async function getMe(queryClient: QueryClient): Promise<UserRead | null> {
  return queryClient.ensureQueryData<UserRead | null>({
    queryKey: ['auth', 'me'],
    queryFn: async () => {
      const result = await usersCurrentUserApiAuthUsersMeGet()
      return result.data ?? null
    },
    retry: false,
  })
}

/*
 * Route guard: blocks unauthenticated access to protected routes.
 * Uses ensureQueryData so the auth check is deduplicated with the
 * useMe hook running inside the destination component.
 */
export async function requireAuth(queryClient: QueryClient, href: string): Promise<UserRead> {
  const user = await getMe(queryClient)
  if (!user) {
    throw redirect({
      to: '/login',
      search: { redirect: href },
    })
  }
  return user
}

interface RouterContext {
  queryClient: QueryClient
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: () => <Outlet />,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LandingPage,
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  validateSearch: authSearchSchema,
  beforeLoad: async ({ context }) => {
    const user = await getMe(context.queryClient)
    if (user) {
      throw redirect({ to: '/research/new' })
    }
  },
  component: LoginPage,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  validateSearch: authSearchSchema,
  beforeLoad: async ({ context }) => {
    const user = await getMe(context.queryClient)
    if (user) {
      throw redirect({ to: '/research/new' })
    }
  },
  component: RegisterPage,
})

const researchNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/new',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
  },
  component: ResearchInputPage,
})

const jobRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/$jobId',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
  },
  component: JobProgressPage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  researchNewRoute,
  jobRoute,
])

export function createAppRouter(queryClient: QueryClient) {
  return createRouter({
    routeTree,
    context: { queryClient },
  })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
