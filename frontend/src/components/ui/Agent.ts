/**
 * Agent identity is referenced across many components (dots, chips, accents,
 * stepper, audit feed). Centralising the type and the static metadata here
 * keeps role labels and CSS-variable suffixes from drifting between files.
 *
 * The CSS variables themselves (`--scout`, `--scout-soft`, etc.) live in
 * `src/index.css`; this module only describes the agents.
 */

export type Agent = 'scout' | 'scribe' | 'critic'

export interface AgentMeta {
  key: Agent
  initial: string
  name: string
  role: 'Research' | 'Synthesis' | 'Verification'
}

export const AGENTS: Record<Agent, AgentMeta> = {
  scout: { key: 'scout', initial: 'S', name: 'Scout', role: 'Research' },
  scribe: { key: 'scribe', initial: 'B', name: 'Scribe', role: 'Synthesis' },
  critic: { key: 'critic', initial: 'C', name: 'Critic', role: 'Verification' },
}

export const AGENT_ORDER: readonly Agent[] = ['scout', 'scribe', 'critic']
