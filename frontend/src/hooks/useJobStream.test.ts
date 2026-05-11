import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useJobStream } from './useJobStream'

// Minimal stand-in for the browser WebSocket interface we touch. Only the methods/properties exercised by the hook are implemented.
class MockWebSocket {
  static instances: MockWebSocket[] = []

  readyState = 0
  // 0=CONNECTING per the WebSocket spec; matches the constants used in the hook.
  readonly url: string
  private listeners: Record<string, Array<(event: unknown) => void>> = {}
  closeArgs: number | undefined

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  addEventListener(type: string, handler: (event: unknown) => void) {
    ;(this.listeners[type] ??= []).push(handler)
  }

  removeEventListener(type: string, handler: (event: unknown) => void) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((h) => h !== handler)
  }

  close(code = 1000) {
    this.closeArgs = code
    this.readyState = 3
    this.dispatch('close', { code })
  }

  // Test helpers (not part of WebSocket).
  open() {
    this.readyState = 1
    this.dispatch('open', {})
  }

  emitMessage(data: string) {
    this.dispatch('message', { data })
  }

  emitError() {
    this.dispatch('error', {})
  }

  private dispatch(type: string, payload: unknown) {
    for (const handler of this.listeners[type] ?? []) handler(payload)
  }
}

afterEach(() => {
  vi.useRealTimers()
  MockWebSocket.instances = []
})

const factory = (url: string) => new MockWebSocket(url) as unknown as WebSocket

describe('useJobStream', () => {
  it('connects to /ws/jobs/{jobId} relative to the current origin', () => {
    renderHook(() => useJobStream('abc-123', { factory }))
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.instances[0]!.url).toMatch(/\/ws\/jobs\/abc-123$/)
    expect(MockWebSocket.instances[0]!.url).toMatch(/^ws:\/\//)
  })

  it('reflects connection lifecycle in status', () => {
    const { result } = renderHook(() => useJobStream('j', { factory }))
    expect(result.current.status).toBe('connecting')

    act(() => MockWebSocket.instances[0]!.open())
    expect(result.current.status).toBe('open')

    act(() => MockWebSocket.instances[0]!.close())
    expect(result.current.status).toBe('closed')
  })

  it('appends well-formed messages and ignores junk', () => {
    const { result } = renderHook(() => useJobStream('j', { factory }))
    const ws = MockWebSocket.instances[0]!

    act(() => ws.emitMessage(JSON.stringify({ type: 'snapshot', job_id: 'j' })))
    act(() =>
      ws.emitMessage(
        JSON.stringify({
          type: 'sub_questions_generated',
          job_id: 'j',
          sub_questions: ['q1'],
        }),
      ),
    )
    // Junk that should be dropped without throwing or affecting state.
    act(() => ws.emitMessage('not json'))
    act(() => ws.emitMessage(JSON.stringify({ type: 'totally_unknown' })))
    act(() => ws.emitMessage(JSON.stringify(null)))

    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[0]?.type).toBe('snapshot')
    expect(result.current.messages[1]?.type).toBe('sub_questions_generated')
  })

  it('closes the socket on unmount', () => {
    const { unmount } = renderHook(() => useJobStream('j', { factory }))
    const ws = MockWebSocket.instances[0]!
    act(() => ws.open())
    unmount()
    expect(ws.closeArgs).toBe(1000)
  })

  it('flips to error status when the socket errors', () => {
    const { result } = renderHook(() => useJobStream('j', { factory }))
    act(() => MockWebSocket.instances[0]!.emitError())
    expect(result.current.status).toBe('error')
  })

  it('reconnects with backoff after an abnormal close', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useJobStream('j', { factory }))
    const first = MockWebSocket.instances[0]!

    act(() => first.emitMessage(JSON.stringify({ type: 'snapshot', job_id: 'j' })))
    expect(result.current.messages).toHaveLength(1)

    act(() => first.close(1006))
    expect(result.current.status).toBe('connecting')
    expect(result.current.messages).toHaveLength(0)
    expect(MockWebSocket.instances).toHaveLength(1)

    act(() => vi.advanceTimersByTime(1000))
    expect(MockWebSocket.instances).toHaveLength(2)
    expect(MockWebSocket.instances[1]!.url).toMatch(/\/ws\/jobs\/j$/)
  })

  it('stops reconnecting after the retry budget is exhausted', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useJobStream('j', { factory }))

    act(() => MockWebSocket.instances[0]!.close(1006))
    act(() => vi.advanceTimersByTime(1000))
    act(() => MockWebSocket.instances[1]!.close(1006))
    act(() => vi.advanceTimersByTime(2000))
    act(() => MockWebSocket.instances[2]!.close(1006))
    act(() => vi.advanceTimersByTime(4000))
    act(() => MockWebSocket.instances[3]!.close(1006))

    expect(result.current.status).toBe('closed')
    expect(MockWebSocket.instances).toHaveLength(4)
  })

  it('restores the retry budget after a reconnect opens', () => {
    vi.useFakeTimers()
    renderHook(() => useJobStream('j', { factory }))

    act(() => MockWebSocket.instances[0]!.close(1006))
    act(() => vi.advanceTimersByTime(1000))
    act(() => MockWebSocket.instances[1]!.open())
    act(() => MockWebSocket.instances[1]!.close(1006))
    act(() => vi.advanceTimersByTime(1000))

    expect(MockWebSocket.instances).toHaveLength(3)
  })

  it('does not reconnect after a normal close', () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useJobStream('j', { factory }))

    act(() => MockWebSocket.instances[0]!.close(1000))
    act(() => vi.runAllTimers())

    expect(result.current.status).toBe('closed')
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('cancels pending reconnects on unmount', () => {
    vi.useFakeTimers()
    const { unmount } = renderHook(() => useJobStream('j', { factory }))

    act(() => MockWebSocket.instances[0]!.close(1006))
    unmount()
    act(() => vi.runAllTimers())

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('falls back to the global WebSocket when no factory is provided', () => {
    const seen: string[] = []
    // `new WebSocket(...)` requires the global to be constructable; vi.fn() returns a plain function and would throw.
    class StubGlobalWs extends MockWebSocket {
      constructor(url: string) {
        super(url)
        seen.push(url)
      }
    }
    vi.stubGlobal('WebSocket', StubGlobalWs)
    try {
      renderHook(() => useJobStream('xyz'))
      expect(seen).toHaveLength(1)
      expect(seen[0]).toMatch(/\/ws\/jobs\/xyz$/)
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
