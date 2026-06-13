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

import FollowUpPage from './pages/FollowUpPage'
import HistoryPage from './pages/HistoryPage'
import JobProgressPage from './pages/JobProgressPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ReportPage from './pages/ReportPage'
import ResearchInputPage from './pages/ResearchInputPage'
import ResearchPreviewPage from './pages/ResearchPreviewPage'
import { previewStateSchema } from './pages/researchPreviewState'

const authSearchSchema = z.object({
  email: z.string().optional(),
  redirect: z.string().optional(),
})

function getSafeAuthRedirect(redirectTo: string | undefined): string {
  if (!redirectTo || !redirectTo.startsWith('/') || redirectTo.startsWith('//')) {
    return '/research/new'
  }
  return redirectTo
}

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
  beforeLoad: async ({ context, search }) => {
    const user = await getMe(context.queryClient)
    if (user) {
      throw redirect({ to: getSafeAuthRedirect(search.redirect) })
    }
  },
  component: LoginPage,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  validateSearch: authSearchSchema,
  beforeLoad: async ({ context, search }) => {
    const user = await getMe(context.queryClient)
    if (user) {
      throw redirect({ to: getSafeAuthRedirect(search.redirect) })
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

const researchPreviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/preview',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
    // The preview screen is only meaningful when reached via router state
    // pushed from `/research/new`; a direct URL hit (or stale tab) carries
    // no plan to review, so bounce back to the input form before mount.
    if (!previewStateSchema.safeParse(location.state ?? {}).success) {
      throw redirect({ to: '/research/new' })
    }
  },
  component: ResearchPreviewPage,
})

const jobRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/$jobId',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
  },
  component: JobProgressPage,
})

const reportRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/$jobId/report',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
  },
  component: ReportPage,
})

const historyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/history',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
  },
  component: HistoryPage,
})

const followUpRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/$jobId/follow-up',
  beforeLoad: async ({ context, location }) => {
    await requireAuth(context.queryClient, location.href)
  },
  component: FollowUpPage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  researchNewRoute,
  researchPreviewRoute,
  jobRoute,
  reportRoute,
  historyRoute,
  followUpRoute,
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

declare module '@tanstack/history' {
  interface HistoryState {
    formData?: {
      topic: string
      depth: 'shallow' | 'standard' | 'deep'
      language: string
      models: Record<string, string>
    }
    subQuestions?: string[]
  }
}
