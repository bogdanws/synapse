import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TopicForm from './TopicForm'

describe('TopicForm', () => {
  it('disables submit until the topic has at least 3 characters', async () => {
    const onSubmit = vi.fn()
    render(<TopicForm onSubmit={onSubmit} />)

    const button = screen.getByRole('button', { name: /start research/i })
    expect(button).toBeDisabled()

    await userEvent.type(screen.getByLabelText(/research topic/i), 'AI')
    expect(button).toBeDisabled()

    await userEvent.type(screen.getByLabelText(/research topic/i), ' agents')
    expect(button).toBeEnabled()
  })

  it('forwards trimmed topic on submit', async () => {
    const onSubmit = vi.fn()
    render(<TopicForm onSubmit={onSubmit} />)

    await userEvent.type(screen.getByLabelText(/research topic/i), '   Quantum computing   ')
    await userEvent.click(screen.getByRole('button', { name: /start research/i }))

    expect(onSubmit).toHaveBeenCalledWith('Quantum computing')
  })
})
