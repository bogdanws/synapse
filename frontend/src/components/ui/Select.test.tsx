import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'

import { Select, type SelectOption } from './Select'

const DEPTH_OPTIONS: ReadonlyArray<SelectOption<'shallow' | 'standard' | 'deep'>> = [
  { value: 'shallow', label: 'Shallow', description: 'Quick scan' },
  { value: 'standard', label: 'Standard', description: 'Balanced run' },
  { value: 'deep', label: 'Deep', description: 'Exhaustive sweep' },
]

function Harness({ onChange }: { onChange?: (v: 'shallow' | 'standard' | 'deep') => void }) {
  const [value, setValue] = useState<'shallow' | 'standard' | 'deep'>('standard')
  return (
    <Select
      value={value}
      onValueChange={(v) => {
        setValue(v)
        onChange?.(v)
      }}
      options={DEPTH_OPTIONS}
      ariaLabel="Research depth"
    />
  )
}

describe('Select', () => {
  it('renders the trigger with the current label', () => {
    render(<Harness />)
    expect(screen.getByRole('combobox', { name: /research depth/i })).toHaveTextContent('Standard')
  })

  it('opens the popup and shows all options on click', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('combobox', { name: /research depth/i }))

    // Items are rendered as listbox options; descriptions are visible too.
    const listbox = await screen.findByRole('listbox')
    expect(listbox).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /shallow/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /standard/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /deep/i })).toBeInTheDocument()
    expect(screen.getByText('Quick scan')).toBeInTheDocument()
  })

  it('fires onValueChange and updates the trigger label when an option is picked', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)

    await userEvent.click(screen.getByRole('combobox', { name: /research depth/i }))
    await userEvent.click(await screen.findByRole('option', { name: /deep/i }))

    expect(onChange).toHaveBeenCalledWith('deep')
    expect(screen.getByRole('combobox', { name: /research depth/i })).toHaveTextContent('Deep')
  })

  it('respects the disabled prop', () => {
    render(
      <Select
        value="standard"
        onValueChange={() => {}}
        options={DEPTH_OPTIONS}
        ariaLabel="Research depth"
        disabled
      />,
    )
    expect(screen.getByRole('combobox', { name: /research depth/i })).toBeDisabled()
  })

  it('renders a custom trigger via renderTrigger and the whole button is the click target', async () => {
    function CustomHarness() {
      const [value, setValue] = useState<'shallow' | 'standard' | 'deep'>('standard')
      return (
        <Select
          value={value}
          onValueChange={setValue}
          options={DEPTH_OPTIONS}
          ariaLabel="Depth pill"
          renderTrigger={(opt) => (
            <>
              <span data-testid="trigger-label">Depth</span>
              <span data-testid="trigger-value">{opt?.label}</span>
            </>
          )}
        />
      )
    }
    render(<CustomHarness />)

    const trigger = screen.getByRole('combobox', { name: /depth pill/i })
    // Both the label area and the value area are inside the trigger button.
    expect(trigger).toContainElement(screen.getByTestId('trigger-label'))
    expect(trigger).toContainElement(screen.getByTestId('trigger-value'))

    // Clicking the label (not the value) still opens the popup, proving the whole pill is clickable.
    await userEvent.click(screen.getByTestId('trigger-label'))
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
  })

  it('renders descriptions and icons inside option rows', async () => {
    render(
      <Select
        value="standard"
        onValueChange={() => {}}
        options={[
          {
            value: 'shallow',
            label: 'Shallow',
            description: 'Quick scan',
            icon: <span data-testid="icon-shallow">★</span>,
          },
          { value: 'standard', label: 'Standard' },
          { value: 'deep', label: 'Deep' },
        ]}
        ariaLabel="Depth"
      />,
    )
    await userEvent.click(screen.getByRole('combobox', { name: /depth/i }))
    expect(await screen.findByText('Quick scan')).toBeInTheDocument()
    expect(screen.getByTestId('icon-shallow')).toBeInTheDocument()
  })
})
