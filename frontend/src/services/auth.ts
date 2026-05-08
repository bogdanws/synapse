import {
  authCookieLoginApiAuthLoginPost,
  authCookieLogoutApiAuthLogoutPost,
  registerRegisterApiAuthRegisterPost,
} from '../types/api'
import type { UserCreate, UserRead } from '../types/api'

export async function loginUser(credentials: { email: string; password: string }): Promise<void> {
  const res = await authCookieLoginApiAuthLoginPost({
    body: { username: credentials.email, password: credentials.password },
  })

  if ('error' in res && res.error) {
    const status = res.response?.status ?? 0
    const detail = (res.error as { detail?: string | Record<string, string> } | undefined)?.detail

    if (status === 400 || status === 401 || detail === 'LOGIN_BAD_CREDENTIALS') {
      throw new Error('Invalid email or password')
    }
    throw new Error(typeof detail === 'string' ? detail : 'Login failed')
  }
}

export async function registerUser(body: UserCreate): Promise<UserRead> {
  const res = await registerRegisterApiAuthRegisterPost({ body })

  if ('error' in res && res.error) {
    const detail = (res.error as { detail?: string | Record<string, string> } | undefined)?.detail

    if (detail === 'REGISTER_USER_ALREADY_EXISTS') {
      throw new Error('An account with this email already exists')
    }
    throw new Error(typeof detail === 'string' ? detail : 'Registration failed')
  }

  if (!('data' in res) || !res.data) {
    throw new Error('Registration failed')
  }

  return res.data
}

export async function logoutUser(): Promise<void> {
  const res = await authCookieLogoutApiAuthLogoutPost()

  if ('error' in res && res.error) {
    const detail = (res.error as { detail?: string } | undefined)?.detail
    throw new Error(typeof detail === 'string' ? detail : 'Logout failed')
  }
}
