import { useEffect, useState } from 'react'

import type { ClaimFlag } from '../types/api'
import { ConfidenceBar } from './ConfidenceBar'

interface MarginPanelProps {
  claimFlags: ClaimFlag[]
  confidence?: number
}

function verdictAgent(verdict: ClaimFlag['verdict']): string {
  switch (verdict) {
    case 'supported':
      return 'scout'
    case 'partially_supported':
      return 'scribe'
    case 'unsupported':
    case 'contradicted':
      return 'critic'
  }
}

function verdictLabel(verdict: ClaimFlag['verdict']): string {
  switch (verdict) {
    case 'supported':
      return 'VERIFIED'
    case 'partially_supported':
      return 'PARTIAL'
    case 'unsupported':
      return 'UNSUPPORTED'
    case 'contradicted':
      return 'CONTRADICTED'
  }
}

export function MarginPanel({ claimFlags, confidence }: MarginPanelProps) {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(max-width: 900px)').matches
      : false,
  )
  const [mobileExpanded, setMobileExpanded] = useState(confidence === undefined)
  const expanded = !isMobile || mobileExpanded || confidence === undefined

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return undefined
    }

    const mobileQuery = window.matchMedia('(max-width: 900px)')
    const syncMobileState = () => setIsMobile(mobileQuery.matches)

    syncMobileState()
    mobileQuery.addEventListener('change', syncMobileState)
    return () => mobileQuery.removeEventListener('change', syncMobileState)
  }, [])

  return (
    <div className="margin-panel" data-expanded={expanded ? 'true' : 'false'}>
      {confidence !== undefined && (
        <button
          type="button"
          className="margin-panel-confidence"
          aria-expanded={expanded}
          onClick={() => setMobileExpanded((value) => !value)}
          style={{
            borderBottom: '1px solid var(--line-soft)',
          }}
        >
          <div className="flex items-center justify-between gap-3" style={{ marginBottom: 8 }}>
            <span className="micro">Confidence</span>
            <span className="margin-panel-toggle micro">
              {expanded ? 'Hide notes' : 'Show notes'}
            </span>
          </div>
          <ConfidenceBar value={confidence} className="w-full" />
        </button>
      )}

      <div className="margin-panel-annotations">
        {claimFlags.map((flag) => {
          const agent = verdictAgent(flag.verdict)
          return (
            <div
              key={flag.claim_id}
              style={{
                borderLeft: `2px solid var(--${agent})`,
                paddingLeft: 12,
                paddingBottom: 14,
                marginBottom: 18,
              }}
            >
              <div
                className="font-mono mb-1"
                style={{ fontSize: 9, letterSpacing: '0.12em', color: `var(--${agent})` }}
              >
                {verdictLabel(flag.verdict)}
              </div>
              <div
                className="serif"
                style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--fg-2)' }}
              >
                {flag.rationale}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
