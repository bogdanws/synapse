/* Barrel for the UI primitives. Imports stay short at call sites:
 *   import { Button, Chip, AgentDot, Dialog } from '@/components/ui'
 *
 * Dialog is re-bundled here as a namespace object so call sites read
 * `<Dialog.Root>...<Dialog.Content>` while the underlying file exports each
 * part individually (required by React Refresh / Vite HMR rules). */
import {
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogRoot,
  DialogTitle,
  DialogTrigger,
} from './Dialog'

export const Dialog = {
  Root: DialogRoot,
  Trigger: DialogTrigger,
  Close: DialogClose,
  Content: DialogContent,
  Title: DialogTitle,
  Description: DialogDescription,
}

export { AGENTS, AGENT_ORDER, type Agent, type AgentMeta } from './Agent'
export { AgentDot } from './AgentDot'
export { Button } from './Button'
export { Chip } from './Chip'
export { SynapseMark } from './SynapseMark'
export { Tooltip, TooltipProvider, TooltipTrigger } from './Tooltip'
export { cn } from './cn'
