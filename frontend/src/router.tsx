import { Outlet, createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import JobProgressPage from './pages/JobProgressPage'
import ResearchInputPage from './pages/ResearchInputPage'

// Code-based routing (no file-based plugin). Keeps the route tree explicit and avoids the generated `routeTree.gen.ts` file.
const rootRoute = createRootRoute({
  component: () => <Outlet />,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: ResearchInputPage,
})

const jobRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/research/$jobId',
  component: JobProgressPage,
})

const routeTree = rootRoute.addChildren([indexRoute, jobRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
