import { useMemo } from 'react'

import type { ClaimFlag } from '../types/api/types.gen'
import type { JobMessage } from './useJobStream'

export interface SourceEntry {
  id: string
  title: string
  url: string
  credibility: number | null
  relevance: number | null
}

export interface SectionEntry {
  id: string
  heading: string
  body_md: string
}

export type CurrentPhase = 'scout' | 'scribe' | 'critic' | 'done' | 'failed'

export interface DerivedJobState {
  topic: string | null
  currentPhase: CurrentPhase
  subQuestions: string[]
  sources: SourceEntry[]
  sections: SectionEntry[]
  claimFlags: ClaimFlag[]
  overallConfidence: number | null
  sourceCount: number
  wordCount: number
  claimCount: number
  scoutComplete: boolean
  scribeComplete: boolean
  createdAt: string | null
}

// Maps JobStatus (from the snapshot) to our display phase. Handles the gap
// between the backend's vocabulary and the three-phase editorial framing.
function jobStatusToPhase(status: string): CurrentPhase {
  switch (status) {
    case 'pending':
    case 'scouting':
      return 'scout'
    case 'synthesizing':
      return 'scribe'
    case 'critiquing':
      return 'critic'
    case 'completed':
      return 'done'
    case 'failed':
      return 'failed'
    default:
      return 'scout'
  }
}

export function useDerivedJobState(messages: JobMessage[]): DerivedJobState {
  return useMemo(() => {
    let topic: string | null = null
    let currentPhase: CurrentPhase = 'scout'
    let createdAt: string | null = null
    const subQuestions: string[] = []
    // Ordered map: insertion order matches arrival order from the stream.
    const sourcesMap = new Map<string, SourceEntry>()
    const sections: SectionEntry[] = []
    const claimFlags: ClaimFlag[] = []
    let overallConfidence: number | null = null
    let scoutComplete = false
    let scribeComplete = false

    for (const msg of messages) {
      switch (msg.type) {
        case 'snapshot': {
          if (msg.job) {
            topic = msg.job.topic
            if (msg.job.created_at) createdAt = msg.job.created_at
            if (msg.job.status) currentPhase = jobStatusToPhase(msg.job.status)
          }
          break
        }
        case 'sub_questions_generated': {
          if (subQuestions.length === 0) {
            subQuestions.push(...msg.sub_questions)
          }
          break
        }
        case 'source_found': {
          const s = msg.source
          sourcesMap.set(s.id, {
            id: s.id,
            title: s.title,
            url: s.url,
            // SourceFound already carries credibility/relevance from the backend model,
            // but source_scored may arrive later with updated scores — prefer those.
            credibility: s.credibility,
            relevance: s.relevance,
          })
          break
        }
        case 'source_scored': {
          const existing = sourcesMap.get(msg.source_id)
          if (existing) {
            sourcesMap.set(msg.source_id, {
              ...existing,
              credibility: msg.credibility,
              relevance: msg.relevance,
            })
          }
          break
        }
        case 'scout_complete': {
          scoutComplete = true
          currentPhase = 'scribe'
          break
        }
        case 'section_drafted': {
          const sec = msg.section
          sections.push({ id: sec.id, heading: sec.heading, body_md: sec.body_md })
          break
        }
        case 'scribe_complete': {
          scribeComplete = true
          currentPhase = 'critic'
          break
        }
        case 'claim_verified': {
          claimFlags.push(msg.flag)
          break
        }
        case 'job_completed': {
          overallConfidence = msg.overall_confidence
          currentPhase = 'done'
          break
        }
        case 'job_failed': {
          currentPhase = 'failed'
          break
        }
        default: {
          // Exhaustiveness guard — new event variants added to the union will cause a compile error here.
          const _exhaustive: never = msg
          void _exhaustive
        }
      }
    }

    const sources = Array.from(sourcesMap.values())
    const wordCount = sections.reduce((total, sec) => {
      // Rough word count by splitting on whitespace sequences.
      return total + sec.body_md.split(/\s+/).filter(Boolean).length
    }, 0)

    return {
      topic,
      currentPhase,
      subQuestions,
      sources,
      sections,
      claimFlags,
      overallConfidence,
      sourceCount: sources.length,
      wordCount,
      claimCount: claimFlags.length,
      scoutComplete,
      scribeComplete,
      createdAt,
    }
  }, [messages])
}
