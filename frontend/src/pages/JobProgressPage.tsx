import { useParams } from '@tanstack/react-router'

import { useJobStream, type JobMessage } from '../hooks/useJobStream'

export default function JobProgressPage() {
  const { jobId } = useParams({ from: '/research/$jobId' })
  const { messages, status } = useJobStream(jobId)

  const completed = messages.find((m) => m.type === 'job_completed')
  const sections = messages.filter((m) => m.type === 'section_drafted')

  return (
    <main>
      <h1>Research progress</h1>
      <p>
        Job <code>{jobId}</code>
      </p>
      <p aria-label="connection status">Connection: {status}</p>
      <ol aria-label="progress events">
        {messages.map((message, index) => (
          // Server messages have no stable id; the index is acceptable because the list is append-only and never reorders.
          <li key={index}>
            <strong>{message.type}</strong> — {summarise(message)}
          </li>
        ))}
      </ol>
      {completed && (
        <section aria-label="raw report dump">
          <h2>Raw report</h2>
          {sections.map((m) => {
            // Narrowed above by the filter; the cast avoids re-narrowing inside map.
            const s = (m as Extract<JobMessage, { type: 'section_drafted' }>).section
            return (
              <details key={s.id} open>
                <summary>
                  <strong>{s.heading}</strong>
                </summary>
                <pre style={{ whiteSpace: 'pre-wrap' }}>{s.body_md}</pre>
              </details>
            )
          })}
        </section>
      )}
    </main>
  )
}

function summarise(message: JobMessage): string {
  switch (message.type) {
    case 'snapshot':
      return message.job ? `status ${message.job.status}` : 'awaiting first event'
    case 'sub_questions_generated':
      return `${message.sub_questions.length} sub-questions`
    case 'source_found':
      return message.source.title
    case 'source_scored':
      return `${message.source_id}: credibility ${message.credibility.toFixed(2)}, relevance ${message.relevance.toFixed(2)}`
    case 'scout_complete':
      return `${message.source_count} sources gathered`
    case 'section_drafted':
      return message.section.heading
    case 'scribe_complete':
      return 'report drafted'
    case 'claim_verified':
      return `${message.flag.claim_id}: ${message.flag.verdict}`
    case 'job_completed':
      return `done (confidence ${message.overall_confidence.toFixed(2)})`
    case 'job_failed':
      return message.error
    default: {
      // Exhaustiveness guard; if a new variant lands without a case here, tsc fails.
      const _exhaustive: never = message
      return String(_exhaustive)
    }
  }
}
