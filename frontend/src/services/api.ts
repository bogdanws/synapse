import type { ResearchJob, ResearchRequest } from '../types/api'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(path, { ...init, headers })
  if (!response.ok) {
    const body = await response.text().catch(() => '')
    let detail = ''
    try {
      const json = JSON.parse(body) as Record<string, unknown>
      detail = String(json.detail ?? json.message ?? json.error ?? '')
    } catch {
      // non-JSON error body (e.g. HTML from a proxy); ignore
    }
    throw new ApiError(
      `Request failed: ${response.status}${detail ? ` — ${detail}` : ''}`,
      response.status,
    )
  }
  return (await response.json()) as T
}

export const api = {
  startResearch(payload: ResearchRequest): Promise<ResearchJob> {
    return request<ResearchJob>('/api/research', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
