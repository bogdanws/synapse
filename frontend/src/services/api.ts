import type { ResearchJobResponse, ResearchRequest } from '../types/api'
import { API_BASE_URL } from '../config/env'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!response.ok) {
    throw new ApiError(`Request failed: ${response.statusText}`, response.status)
  }
  return (await response.json()) as T
}

export const api = {
  startResearch(payload: ResearchRequest): Promise<ResearchJobResponse> {
    return request<ResearchJobResponse>('/api/research', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
