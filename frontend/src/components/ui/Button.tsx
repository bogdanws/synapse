import type { ButtonHTMLAttributes } from 'react'

import { cn } from './cn'

type Variant = 'primary' | 'ghost'
type Size = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

/*
 * Editorial button: square corners, single-pixel border, slight lift on hover.
 * Matches the `.btn` rule from example_frontend/tokens.jsx — primary inverts
 * fg/bg, ghost is transparent with the foreground colour.
 *
 * Padding tracks the size prop, not a Tailwind preset, because the example
 * uses 12/18 (md) and 8/12 (sm) which don't map cleanly onto Tailwind's scale
 * and we want to honour the figma exactly.
 */
export function Button({
  className,
  variant = 'primary',
  size = 'md',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center gap-2 border font-sans text-[13px] cursor-pointer transition-transform duration-[120ms]',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0',
        'hover:-translate-y-px',
        size === 'md' && 'px-[18px] py-3',
        size === 'sm' && 'px-3 py-2',
        variant === 'primary' && 'bg-fg text-bg border-fg',
        variant === 'ghost' && 'bg-transparent text-fg border-fg',
        className,
      )}
      style={{ letterSpacing: '-0.005em' }}
      {...props}
    />
  )
}
