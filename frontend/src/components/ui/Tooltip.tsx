import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip'
import type { ComponentProps, ReactNode } from 'react'

import { cn } from './cn'

/*
 * Base UI tooltip styled as a small ink chip. Anchored via Base UI's floating
 * positioner, so it auto-flips at the viewport edges — used heavily on the
 * report viewer to surface claim flags inline.
 *
 * `<Tooltip.Provider>` should sit once near the app root; individual tooltips
 * use `<Tooltip>` which is shorthand for Root + Portal + Positioner + Popup.
 */

const Provider = BaseTooltip.Provider
const Trigger = BaseTooltip.Trigger

interface TooltipProps extends ComponentProps<typeof BaseTooltip.Root> {
  content: ReactNode
  children: ReactNode
  className?: string
}

function Tooltip({ content, children, className, ...rootProps }: TooltipProps) {
  return (
    <BaseTooltip.Root {...rootProps}>
      <BaseTooltip.Trigger render={<span>{children}</span>} />
      <BaseTooltip.Portal>
        <BaseTooltip.Positioner sideOffset={8}>
          <BaseTooltip.Popup
            className={cn(
              'bg-fg text-bg font-mono text-[10px] uppercase tracking-[0.08em]',
              'px-2 py-1.5 max-w-[260px] leading-snug',
              'data-[ending-style]:opacity-0 data-[starting-style]:opacity-0',
              'transition-opacity duration-150',
              className,
            )}
          >
            {content}
          </BaseTooltip.Popup>
        </BaseTooltip.Positioner>
      </BaseTooltip.Portal>
    </BaseTooltip.Root>
  )
}

export { Tooltip, Provider as TooltipProvider, Trigger as TooltipTrigger }
