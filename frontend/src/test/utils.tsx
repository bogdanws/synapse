import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { render } from '@testing-library/react'

export function renderWithRouter(
  ui: React.ReactNode,
  {
    path = '/',
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  }: { path?: string; queryClient?: QueryClient } = {},
) {
  const root = createRootRoute({ component: () => <Outlet /> })
  const route = createRoute({
    getParentRoute: () => root,
    path,
    component: () => ui,
  })

  const router = createRouter({
    routeTree: root.addChildren([route]),
    context: { queryClient },
  })

  router.navigate({ to: path })

  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
    router,
    queryClient,
  }
}
