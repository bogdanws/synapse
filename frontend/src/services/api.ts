import type { ResearchJob, ResearchRequest } from '../types/api'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Shape of a result from the generated openapi-ts client. The client returns
 * `{ data, error, response }` instead of throwing on non-2xx; callers must
 * inspect both branches. Narrowed here to the fields we actually use.
 */
interface ClientResult<T> {
  data?: T
  error?: unknown
  response?: { status: number }
}

/**
 * Bridge an openapi-ts client result into the `ApiError` contract the rest of
 * the app already uses (see `ReportPage` checking `error instanceof ApiError`
 * with `error.status === 404`). Returns `result.data` on success; throws an
 * `ApiError` carrying the HTTP status and the server's `detail` field on
 * failure so React Query / mutations can surface the real cause.
 */
export function unwrapClientResult<T>(result: ClientResult<T>): T {
  if (result.error !== undefined && result.error !== null) {
    const status = result.response?.status ?? 0
    const detail = extractDetail(result.error)
    throw new ApiError(`Request failed: ${status}${detail ? ` — ${detail}` : ''}`, status)
  }
  if (result.data === undefined) {
    // 2xx with no body is unusual for our endpoints; treat as an unexpected
    // server contract violation rather than silently returning undefined.
    const status = result.response?.status ?? 0
    throw new ApiError('Request returned no data', status)
  }
  return result.data
}

function extractDetail(error: unknown): string {
  if (typeof error === 'string') return error
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      // FastAPI 422 returns an array of `{loc, msg, type}` items.
      const first = detail[0] as { msg?: unknown } | undefined
      if (first && typeof first.msg === 'string') return first.msg
    }
  }
  return ''
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
