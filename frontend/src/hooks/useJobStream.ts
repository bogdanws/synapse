import { useEffect, useState } from 'react'

import type { JobSnapshot, ProgressEvent } from '../types/api'

export type JobMessage = JobSnapshot | ProgressEvent
export type ConnectionStatus = 'connecting' | 'open' | 'closed' | 'error'

interface UseJobStreamOptions {
  // Override the WebSocket constructor in tests; defaults to the global.
  factory?: (url: string) => WebSocket
}

interface UseJobStreamResult {
  messages: JobMessage[]
  status: ConnectionStatus
}

const KNOWN_TYPES: ReadonlySet<string> = new Set([
  'snapshot',
  'sub_questions_generated',
  'source_found',
  'source_scored',
  'scout_complete',
  'section_drafted',
  'scribe_complete',
  'claim_verified',
  'job_completed',
  'job_failed',
])

const RECONNECT_DELAYS_MS = [1000, 2000, 4000] as const

function jobsWsUrl(jobId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/jobs/${jobId}`
}

// The wire shape comes from the OpenAPI codegen (JobSnapshot | ProgressEvent), so we trust the static types but still guard the boundary against malformed payloads (network corruption, accidentally redirected route, etc.) by checking the discriminator before accepting a message.
export function useJobStream(jobId: string, options: UseJobStreamOptions = {}): UseJobStreamResult {
  // Both state slices are keyed by jobId so derived values reset correctly when the job changes without a synchronous setState inside the effect
  const [entries, setEntries] = useState<{ jobId: string; messages: JobMessage[] }>({
    jobId,
    messages: [],
  })
  const [statusState, setStatusState] = useState<{ jobId: string; status: ConnectionStatus }>({
    jobId,
    status: 'connecting',
  })
  const messages = entries.jobId === jobId ? entries.messages : []
  const status = statusState.jobId === jobId ? statusState.status : 'connecting'

  useEffect(() => {
    let active = true
    let attempts = 0
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof window.setTimeout> | undefined
    const create = options.factory ?? ((url: string) => new WebSocket(url))

    const connect = () => {
      ws = create(jobsWsUrl(jobId))
      const current = ws

      const onOpen = () => {
        attempts = 0
        setStatusState({ jobId, status: 'open' })
      }
      const onError = () => setStatusState({ jobId, status: 'error' })
      const onClose = (event: CloseEvent) => {
        if (!active) return
        const delay = RECONNECT_DELAYS_MS[attempts]
        if (event.code !== 1000 && delay !== undefined) {
          attempts += 1
          setEntries({ jobId, messages: [] })
          setStatusState({ jobId, status: 'connecting' })
          reconnectTimer = window.setTimeout(connect, delay)
          return
        }
        setStatusState({ jobId, status: 'closed' })
      }
      const onMessage = (event: MessageEvent<string>) => {
        const parsed = parseMessage(event.data)
        if (!parsed) return
        setEntries((prev) =>
          prev.jobId === jobId
            ? { jobId, messages: [...prev.messages, parsed] }
            : { jobId, messages: [parsed] },
        )
      }

      current.addEventListener('open', onOpen)
      current.addEventListener('error', onError)
      current.addEventListener('close', onClose)
      current.addEventListener('message', onMessage)
    }

    connect()

    return () => {
      active = false
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      // 1000 = normal closure. Calling close on an already-closed socket is a no-op.
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.close(1000)
      }
    }
  }, [jobId, options.factory])

  return { messages, status }
}

function parseMessage(raw: unknown): JobMessage | null {
  if (typeof raw !== 'string') return null
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof parsed !== 'object' || parsed === null) return null
  const candidate = parsed as { type?: unknown }
  if (typeof candidate.type !== 'string' || !KNOWN_TYPES.has(candidate.type)) return null
  return parsed as JobMessage
}
