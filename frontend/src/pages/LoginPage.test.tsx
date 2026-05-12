import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import LoginPage from './LoginPage'

vi.mock('../types/api', () => ({
  authCookieLoginApiAuthLoginPost: vi.fn(),
}))

const mockNavigate = vi.fn()
const mockSearch = { redirect: undefined as string | undefined }

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearch: () => mockSearch,
    Link: ({
      children,
      ...props
    }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children?: React.ReactNode }) => (
      <a {...props}>{children}</a>
    ),
  }
})

import { authCookieLoginApiAuthLoginPost } from '../types/api'

function renderPage(
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } }),
) {
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <LoginPage />
      </QueryClientProvider>,
    ),
  }
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(authCookieLoginApiAuthLoginPost).mockReset()
    mockSearch.redirect = undefined
  })

  it('renders the sign-in form', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('validates required fields', async () => {
    renderPage()

    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
      expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument()
    })
  })

  it('calls login on submit', async () => {
    vi.mocked(authCookieLoginApiAuthLoginPost).mockResolvedValue({
      data: {},
      response: { ok: true, status: 204 } as Response,
      request: {} as Request,
    } as never)

    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(authCookieLoginApiAuthLoginPost).toHaveBeenCalledWith({
        body: { username: 'test@example.com', password: 'password123' },
      })
    })
  })

  it('redirects on success', async () => {
    vi.mocked(authCookieLoginApiAuthLoginPost).mockResolvedValue({
      data: {},
      response: { ok: true, status: 204 } as Response,
      request: {} as Request,
    } as never)

    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
    })
  })

  it('clears cached anonymous auth state before redirecting', async () => {
    vi.mocked(authCookieLoginApiAuthLoginPost).mockResolvedValue({
      data: {},
      response: { ok: true, status: 204 } as Response,
      request: {} as Request,
    } as never)

    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    queryClient.setQueryData(['auth', 'me'], null)
    renderPage(queryClient)

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(queryClient.getQueryData(['auth', 'me'])).toBeUndefined()
      expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
    })
  })

  it('redirects to the search redirect param on success', async () => {
    vi.mocked(authCookieLoginApiAuthLoginPost).mockResolvedValue({
      data: {},
      response: { ok: true, status: 204 } as Response,
      request: {} as Request,
    } as never)

    mockSearch.redirect = '/research/new'
    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
    })
  })

  it('shows error on bad credentials', async () => {
    vi.mocked(authCookieLoginApiAuthLoginPost).mockResolvedValue({
      error: { detail: 'LOGIN_BAD_CREDENTIALS' },
      response: { status: 400, ok: false } as Response,
      request: {} as Request,
    } as never)

    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid email or password/i)
    })
  })
})
