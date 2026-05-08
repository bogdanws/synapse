import { useState } from 'react'
import TopicForm from '../components/TopicForm'
import { api, ApiError } from '../services/api'
import type { ResearchJob } from '../types/api'

export default function ResearchInputPage() {
  const [job, setJob] = useState<ResearchJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (topic: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.startResearch({ topic })
      setJob(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unexpected error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <TopicForm onSubmit={handleSubmit} disabled={loading} />
      {error && <p role="alert">{error}</p>}
      {job && (
        <section aria-live="polite">
          <p>id: {job.id}</p>
          <p>status: {job.status}</p>
        </section>
      )}
    </main>
  )
}
