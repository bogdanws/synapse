import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import TopicForm from '../components/TopicForm'
import { ApiError, api } from '../services/api'

export default function ResearchInputPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (topic: string) => {
    setLoading(true)
    setError(null)
    try {
      const job = await api.startResearch({ topic })
      await navigate({ to: '/research/$jobId', params: { jobId: job.id } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unexpected error')
      setLoading(false)
    }
  }

  return (
    <main>
      <TopicForm onSubmit={handleSubmit} disabled={loading} />
      {error && <p role="alert">{error}</p>}
    </main>
  )
}
