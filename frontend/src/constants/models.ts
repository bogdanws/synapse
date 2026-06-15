import type { Agent } from '../components/ui/Agent'

/*
 * Development-only allow-list of OpenRouter model IDs.
 * Backend validation of these IDs is a follow-up to prevent misuse.
 */
export const ALLOWED_MODELS = [
  { id: 'openrouter/free', label: 'OpenRouter Free' },
  { id: 'nvidia/nemotron-3-ultra-550b-a55b:free', label: 'Nemotron 3 Ultra Free' },
  { id: 'google/gemini-3.1-flash-lite', label: 'Gemini 3.1 Flash Lite' },
  { id: 'qwen/qwen3.7-plus', label: 'Qwen 3.7 Plus' },
  { id: 'openai/gpt-4o-mini', label: 'GPT-4o mini' },
  { id: 'deepseek/deepseek-v4-pro', label: 'DeepSeek v4 Pro' },
  { id: 'minimax/minimax-m3', label: 'MiniMax M3' },
  { id: 'anthropic/claude-haiku-4.5', label: 'Claude Haiku 4.5' },
  { id: 'openai/gpt-5.4-nano', label: 'GPT-5.4 Nano' },
] as const

export const MODEL_STORAGE_KEY = 'synapse:agent-models:v1'

export const DEFAULT_AGENT_MODELS: Record<Agent, string> = {
  scout: 'openrouter/free',
  scribe: 'openrouter/free',
  critic: 'openrouter/free',
}
