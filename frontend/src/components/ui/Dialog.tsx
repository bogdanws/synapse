import { Dialog as BaseDialog } from '@base-ui/react/dialog'
import type { ComponentProps, ReactNode } from 'react'

import { cn } from './cn'

/* Base UI accepts `className` as either a string or a state-aware function.
 * Our wrappers only ever forward a static class, so narrowing here keeps the
 * call-site API simple and lets `cn()` stay strictly string-typed. */
type StaticClassNameProps<T> = Omit<T, 'className'> & { className?: string }

/*
 * Editorial dialog: ivory popup, 1px line border, faintly inked backdrop, no
 * rounded corners. The Tailwind layer below is the entire visual surface;
 * Base UI handles focus trapping, scroll lock, escape, and aria roles.
 *
 * Components are exported individually (rather than under a namespace object)
 * so the file plays nicely with React Refresh / HMR. The `index.ts` barrel
 * re-bundles them as `Dialog.*` for ergonomic call sites.
 */

/* Direct passthroughs to Base UI's headless parts. Wrapped as named functions
 * (not `const` aliases) so the React Refresh ESLint rule treats them as
 * components and HMR keeps working. */
export function DialogRoot(props: ComponentProps<typeof BaseDialog.Root>) {
  return <BaseDialog.Root {...props} />
}

export function DialogTrigger(props: ComponentProps<typeof BaseDialog.Trigger>) {
  return <BaseDialog.Trigger {...props} />
}

export function DialogClose(props: ComponentProps<typeof BaseDialog.Close>) {
  return <BaseDialog.Close {...props} />
}

export function DialogContent({
  children,
  className,
  ...props
}: StaticClassNameProps<ComponentProps<typeof BaseDialog.Popup>> & {
  children: ReactNode
}) {
  return (
    <BaseDialog.Portal>
      <BaseDialog.Backdrop className="fixed inset-0 bg-fg/40 backdrop-blur-[1px] data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 transition-opacity duration-200" />
      <BaseDialog.Popup
        className={cn(
          'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2',
          'w-[min(560px,calc(100vw-32px))] max-h-[calc(100vh-64px)] overflow-y-auto',
          'bg-bg text-fg border border-line p-8',
          'data-[ending-style]:opacity-0 data-[starting-style]:opacity-0',
          'transition-opacity duration-200 outline-none',
          className,
        )}
        {...props}
      >
        {children}
      </BaseDialog.Popup>
    </BaseDialog.Portal>
  )
}

export function DialogTitle({
  className,
  ...props
}: StaticClassNameProps<ComponentProps<typeof BaseDialog.Title>>) {
  return (
    <BaseDialog.Title
      className={cn('font-serif text-3xl font-normal tracking-[-0.02em]', className)}
      {...props}
    />
  )
}

export function DialogDescription({
  className,
  ...props
}: StaticClassNameProps<ComponentProps<typeof BaseDialog.Description>>) {
  return (
    <BaseDialog.Description
      className={cn('text-fg-2 mt-3 leading-relaxed', className)}
      {...props}
    />
  )
}
