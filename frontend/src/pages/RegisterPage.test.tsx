import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import RegisterPage from './RegisterPage'

vi.mock('../types/api', () => ({
  authCookieLoginApiAuthLoginPost: vi.fn(),
  registerRegisterApiAuthRegisterPost: vi.fn(),
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

import { authCookieLoginApiAuthLoginPost, registerRegisterApiAuthRegisterPost } from '../types/api'

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <RegisterPage />
    </QueryClientProvider>,
  )
}

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(authCookieLoginApiAuthLoginPost).mockReset()
    vi.mocked(registerRegisterApiAuthRegisterPost).mockReset()
    mockSearch.redirect = undefined
  })

  it('renders the registration form', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
  })

  it('shows error on password confirmation mismatch', async () => {
    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'password123')
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'different')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument()
    })
  })

  it('calls register then login and redirects', async () => {
    vi.mocked(registerRegisterApiAuthRegisterPost).mockResolvedValue({
      data: { id: 'u1', email: 'test@example.com' },
      response: { ok: true, status: 201 } as Response,
      request: {} as Request,
    } as never)

    vi.mocked(authCookieLoginApiAuthLoginPost).mockResolvedValue({
      data: {},
      response: { ok: true, status: 204 } as Response,
      request: {} as Request,
    } as never)

    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'password123')
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(registerRegisterApiAuthRegisterPost).toHaveBeenCalledWith({
        body: { email: 'test@example.com', password: 'password123' },
      })
      expect(authCookieLoginApiAuthLoginPost).toHaveBeenCalledWith({
        body: { username: 'test@example.com', password: 'password123' },
      })
      expect(mockNavigate).toHaveBeenCalledWith({ to: '/research/new' })
    })
  })

  it('shows error on duplicate email', async () => {
    vi.mocked(registerRegisterApiAuthRegisterPost).mockResolvedValue({
      error: { detail: 'REGISTER_USER_ALREADY_EXISTS' },
      response: { status: 400, ok: false } as Response,
      request: {} as Request,
    } as never)

    renderPage()

    await userEvent.type(screen.getByLabelText(/email/i), 'test@example.com')
    await userEvent.type(screen.getByLabelText(/^password$/i), 'password123')
    await userEvent.type(screen.getByLabelText(/confirm password/i), 'password123')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /an account with this email already exists/i,
      )
    })
  })
})
