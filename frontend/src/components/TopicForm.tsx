import { useState, type FormEvent } from 'react'

interface TopicFormProps {
  onSubmit: (topic: string) => void | Promise<void>
  disabled?: boolean
}

export default function TopicForm({ onSubmit, disabled }: TopicFormProps) {
  const [topic, setTopic] = useState('')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmed = topic.trim()
    if (trimmed.length < 3) return
    void onSubmit(trimmed)
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="topic">Research topic</label>
      <textarea
        id="topic"
        name="topic"
        value={topic}
        onChange={(event) => setTopic(event.target.value)}
        rows={3}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || topic.trim().length < 3}>
        Start research
      </button>
    </form>
  )
}
