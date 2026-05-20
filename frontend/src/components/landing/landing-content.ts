export type AgentKey = 'scout' | 'scribe' | 'critic'

export interface AgentCard {
  key: AgentKey
  num: string
  name: string
  role: string
  brief: string
  ops: readonly string[]
}

export const AGENT_CARDS: readonly AgentCard[] = [
  {
    key: 'scout',
    num: 'I.',
    name: 'Scout',
    role: 'Research Agent',
    brief:
      'Decomposes the topic into sub-questions, hunts across the open web, archives, APIs, and weighs each source for credibility before passing it on.',
    ops: [
      'decompose(topic)',
      'search(web, archives, APIs)',
      'score(credibility, recency)',
      'dedupe & rank',
    ],
  },
  {
    key: 'scribe',
    num: 'II.',
    name: 'Scribe',
    role: 'Synthesis Agent',
    brief:
      'Reads the dossier, drafts a structured report with inline citations, surfaces contradictions, and writes a tight executive summary.',
    ops: [
      'outline(sections)',
      'draft(with_citations)',
      'summarise(executive)',
      'flag(contradictions)',
    ],
  },
  {
    key: 'critic',
    num: 'III.',
    name: 'Critic',
    role: 'Fact‑Checking Agent',
    brief:
      'Audits every sentence against original sources, marks unsupported claims, and assigns a confidence score per section.',
    ops: [
      'verify(claim ↔ source)',
      'detect(hallucinations)',
      'score(confidence)',
      'annotate(margin)',
    ],
  },
]

export interface MethodStep {
  n: string
  t: string
  who: AgentKey | null
  body: string
}

export const METHOD_STEPS: readonly MethodStep[] = [
  {
    n: '00',
    t: 'Brief',
    who: null,
    body: 'You write a topic and any constraints — depth, recency, sources to avoid.',
  },
  {
    n: '01',
    t: 'Decompose & gather',
    who: 'scout',
    body: 'Scout splits the question into 8–24 sub-queries and pulls 60–200 sources.',
  },
  {
    n: '02',
    t: 'Synthesise',
    who: 'scribe',
    body: 'Scribe drafts the report — sections, citations, executive summary, open questions.',
  },
  {
    n: '03',
    t: 'Audit',
    who: 'critic',
    body: 'Critic re-reads every claim against its source, scores confidence, flags drift.',
  },
  {
    n: '04',
    t: 'Delivered',
    who: null,
    body: 'You receive an annotated report with confidence per section and a list of caveats.',
  },
]

export interface FeaturePillar {
  title: string
  body: string
  tag: string
}

export const FEATURE_PILLARS: readonly FeaturePillar[] = [
  {
    title: 'Cited claims',
    body: 'Every assertion in the final report is anchored to the source that supports it. Nothing clears the Critic without a traceable citation.',
    tag: 'Scout → Scribe',
  },
  {
    title: 'Adversarial audit',
    body: 'Scout and Scribe build the case; Critic is explicitly tasked with finding what they got wrong. The disagreement happens inside the pipeline — before it reaches you.',
    tag: 'Critic',
  },
  {
    title: 'Confidence by section',
    body: 'Each section of the report carries a score and a set of margin annotations, so you know exactly where to push back and where to trust the output.',
    tag: 'Critic → output',
  },
]

export interface ConstellationAgent {
  key: AgentKey
  name: string
  role: string
  pos: { x: number; y: number }
}

export const CONSTELLATION_AGENTS: readonly ConstellationAgent[] = [
  { key: 'scout', name: 'Scout', role: 'researches', pos: { x: 90, y: 87 } },
  { key: 'scribe', name: 'Scribe', role: 'synthesises', pos: { x: 350, y: 110 } },
  { key: 'critic', name: 'Critic', role: 'verifies', pos: { x: 220, y: 248 } },
]

export const THIS_WEEK = [
  'What changed in EU AI policy this quarter?',
  'How is the GLP-1 market shifting in 2026?',
  'Where is venture capital flowing in CEE?',
  "What's the state of Asia–Europe shipping?",
] as const
