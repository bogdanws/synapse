import { Select as BaseSelect } from '@base-ui/react/select'
import type { ReactNode } from 'react'

import { cn } from './cn'

export interface SelectOption<T extends string = string> {
  value: T
  label: string
  /** Optional secondary line beneath the label (mono, muted). Used to surface model IDs in the popup. */
  description?: string
  /** Optional leading icon node rendered before the label in the popup row. */
  icon?: ReactNode
  /** Disable this individual option. */
  disabled?: boolean
}

interface SelectProps<T extends string> {
  value: T
  onValueChange: (value: T) => void
  options: ReadonlyArray<SelectOption<T>>
  placeholder?: string
  disabled?: boolean
  ariaLabel?: string
  /** Caps the default value text with ellipsis. Ignored when `renderTrigger` is provided. */
  triggerMaxWidth?: number
  /** Class names applied to the trigger `<button>`. Use this to size, border, pad the trigger. */
  triggerClassName?: string
  /** Class names applied to the popup. Useful for setting a wider `min-w-…`. */
  popupClassName?: string
  /**
   * Custom content for the trigger body. The caret is always appended at the end of the
   * button so callers don't have to render it themselves. The argument is the currently
   * selected option (or `undefined` if no value matches).
   */
  renderTrigger?: (selected: SelectOption<T> | undefined) => ReactNode
  /** Hide the trailing caret icon. Default false. */
  hideCaret?: boolean
}

/*
 * Editorial select. By default, the trigger is plain text + a faint caret —
 * meant to drop into a settings row without competing with surrounding chrome.
 * For richer call sites (e.g. a pill-shaped trigger with a label above the
 * value), pass `renderTrigger` and `triggerClassName`: the entire button
 * becomes the click target, so hover and focus light up the whole shape
 * instead of just the value text.
 *
 * The popup is a stamped ivory card with a 1px ink border and a 4px offset
 * "second sheet" — the design system rejects CSS drop shadows, so we draw
 * the lift with two layered box-shadows of theme colours instead.
 *
 * Implementation note: Base UI's headless Select gives us keyboard nav, focus
 * management, scroll locking and a hidden form input for free.
 */
export function Select<T extends string>({
  value,
  onValueChange,
  options,
  placeholder,
  disabled,
  ariaLabel,
  triggerMaxWidth,
  triggerClassName,
  popupClassName,
  renderTrigger,
  hideCaret,
}: SelectProps<T>) {
  // Items dict lets `<Select.Value>` render the selected label automatically
  // for the default trigger. Render functions / `renderTrigger` bypass this.
  const items: Record<string, ReactNode> = Object.fromEntries(
    options.map((o) => [o.value, o.label]),
  )

  const selected = options.find((o) => o.value === value)

  return (
    <BaseSelect.Root
      value={value}
      onValueChange={(next) => {
        if (next != null) onValueChange(next as T)
      }}
      disabled={disabled}
      items={items}
    >
      <BaseSelect.Trigger
        aria-label={ariaLabel}
        className={cn(
          'inline-flex items-center gap-1.5 bg-transparent font-sans text-[12px] text-left',
          'outline-none cursor-pointer transition-colors duration-150',
          'text-fg',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          // When using the default trigger (no renderTrigger), give the value a subtle hover/focus cue.
          !renderTrigger &&
            'hover:text-fg-2 focus-visible:underline focus-visible:underline-offset-[3px]',
          triggerClassName,
        )}
        style={{ letterSpacing: '-0.005em' }}
      >
        {renderTrigger ? (
          renderTrigger(selected)
        ) : (
          <BaseSelect.Value
            className="block truncate"
            style={triggerMaxWidth ? { maxWidth: triggerMaxWidth } : undefined}
            placeholder={placeholder}
          />
        )}
        {!hideCaret && (
          <BaseSelect.Icon
            className="shrink-0 inline-flex ml-auto transition-transform duration-150 data-[popup-open]:rotate-180"
            style={{ color: 'var(--muted)' }}
          >
            <svg width="9" height="6" viewBox="0 0 9 6" fill="none" aria-hidden>
              <path
                d="M1 1.25L4.5 4.75L8 1.25"
                stroke="currentColor"
                strokeWidth="1"
                strokeLinecap="square"
              />
            </svg>
          </BaseSelect.Icon>
        )}
      </BaseSelect.Trigger>

      <BaseSelect.Portal>
        <BaseSelect.Positioner
          sideOffset={6}
          align="start"
          alignItemWithTrigger={false}
          className="outline-none z-50"
        >
          <BaseSelect.Popup
            className={cn(
              'scrollbar font-sans text-[13px] outline-none',
              'min-w-[var(--anchor-width)]',
              'data-[ending-style]:opacity-0 data-[starting-style]:opacity-0',
              'data-[ending-style]:translate-y-[-2px] data-[starting-style]:translate-y-[-2px]',
              'transition-[opacity,transform] duration-150 ease-out',
              'max-h-[min(320px,60vh)] overflow-auto',
              popupClassName,
            )}
            style={{
              background: 'var(--bg)',
              color: 'var(--fg)',
              border: '1px solid var(--fg)',
              letterSpacing: '-0.005em',
              // Faint second-sheet to lift the popup off the page without a CSS drop shadow.
              boxShadow: '4px 4px 0 0 var(--bg-2), 4px 4px 0 1px var(--line)',
            }}
          >
            <BaseSelect.List className="py-1">
              {options.map((opt, i) => (
                <BaseSelect.Item
                  key={opt.value}
                  value={opt.value}
                  disabled={opt.disabled}
                  className={cn(
                    'flex items-center gap-2.5 px-3 py-2 cursor-pointer outline-none select-none',
                    'transition-colors',
                    'data-[highlighted]:bg-bg-2',
                    'data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed',
                  )}
                  style={
                    i < options.length - 1
                      ? { borderBottom: '1px solid var(--line-soft)' }
                      : undefined
                  }
                >
                  {/* Fixed-width indicator slot keeps labels aligned whether the row is selected or not. */}
                  <span className="inline-flex w-2 h-2 shrink-0 items-center justify-center">
                    <BaseSelect.ItemIndicator>
                      <span
                        className="inline-block w-[5px] h-[5px] rounded-full"
                        style={{ background: 'var(--fg)' }}
                      />
                    </BaseSelect.ItemIndicator>
                  </span>
                  {opt.icon && (
                    <span className="shrink-0 inline-flex items-center">{opt.icon}</span>
                  )}
                  <span className="flex flex-col min-w-0">
                    <BaseSelect.ItemText className="truncate">{opt.label}</BaseSelect.ItemText>
                    {opt.description && (
                      <span
                        className="font-mono text-[10px] truncate"
                        style={{ color: 'var(--muted)', letterSpacing: '0.04em' }}
                      >
                        {opt.description}
                      </span>
                    )}
                  </span>
                </BaseSelect.Item>
              ))}
            </BaseSelect.List>
          </BaseSelect.Popup>
        </BaseSelect.Positioner>
      </BaseSelect.Portal>
    </BaseSelect.Root>
  )
}
