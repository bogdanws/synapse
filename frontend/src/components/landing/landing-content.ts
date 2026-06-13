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
      'Breaks the topic into smaller questions',
      'Searches the open web, archives, and APIs',
      'Scores each source for credibility and recency',
      'Removes duplicates and ranks the rest',
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
      'Outlines the report into clear sections',
      'Drafts each section with inline citations',
      'Writes a tight executive summary',
      'Flags where sources disagree',
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
      'Checks every claim against its source',
      'Catches unsupported or invented statements',
      'Scores confidence by section',
      'Leaves margin notes on thin claims',
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

export interface PillarOwner {
  label: string
  /** Agent key for tinting, or null for non-agent stages like "output". */
  agent: AgentKey | null
}

export interface FeaturePillar {
  title: string
  body: string
  /** Ordered handoff: rendered as a chip line with arrows between entries. */
  owners: readonly PillarOwner[]
}

export const FEATURE_PILLARS: readonly FeaturePillar[] = [
  {
    title: 'Cited claims',
    body: 'Every assertion in the final report is anchored to the source that supports it. Nothing clears the Critic without a traceable citation.',
    owners: [
      { label: 'Scout', agent: 'scout' },
      { label: 'Scribe', agent: 'scribe' },
    ],
  },
  {
    title: 'Adversarial audit',
    body: 'Scout and Scribe build the case; Critic is explicitly tasked with finding what they got wrong. The disagreement happens inside the pipeline — before it reaches you.',
    owners: [{ label: 'Critic', agent: 'critic' }],
  },
  {
    title: 'Confidence by section',
    body: 'Each section of the report carries a score and a set of margin annotations, so you know exactly where to push back and where to trust the output.',
    owners: [
      { label: 'Critic', agent: 'critic' },
      { label: 'Output', agent: null },
    ],
  },
]

/*
 * Pipeline demo data — drives <AgentPipelineHero/>. Each PipelineRun is a
 * scripted, deterministic loop: Scout finds sources, Scribe drafts with
 * inline citations, Critic redlines a phrase and scores confidence. The
 * payload is intentionally hand-authored (not fetched) so the hero looks
 * the same in dev, prod, SSR, and on poor connections.
 */

export interface PipelineSource {
  title: string
  credibility: number
}

interface WordToken {
  kind: 'w'
  text: string
  // When true, this word is part of the phrase the Critic redlines. Authored
  // contiguously per run so the underline draws as one span.
  redline?: true
}
interface CiteToken {
  kind: 'c'
  n: number
}
interface PunctToken {
  kind: 'p'
  text: string
}
export type DraftToken = WordToken | CiteToken | PunctToken

// Tiny authoring helpers — keep the run definitions readable.
const w = (text: string, redline?: boolean): WordToken =>
  redline ? { kind: 'w', text, redline: true } : { kind: 'w', text }
const c = (n: number): CiteToken => ({ kind: 'c', n })
const p = (text: string): PunctToken => ({ kind: 'p', text })

export interface PipelineRun {
  query: string
  sources: readonly PipelineSource[]
  draft: readonly DraftToken[]
  criticNote: string
  /** 0–100 */
  confidence: number
}

export const PIPELINE_RUNS: readonly PipelineRun[] = [
  {
    query: 'What changed in EU AI policy this quarter?',
    sources: [
      { title: 'Eurostat Q3 policy brief', credibility: 94 },
      { title: 'FT — Brussels desk, 2026-03-12', credibility: 91 },
      { title: 'AI Office circular no. 17', credibility: 88 },
      { title: 'Reuters policy wire', credibility: 82 },
    ],
    draft: [
      w('In'),
      w('Q3'),
      w('2026'),
      p(','),
      w('the'),
      w('EU'),
      w('AI'),
      w("Act's"),
      w('enforcement'),
      w('framework'),
      c(1),
      w('shifted', true),
      w('significantly', true),
      c(2),
      p(','),
      w('with'),
      w('the'),
      w('AI'),
      w('Office'),
      c(3),
      w('issuing'),
      w('twelve'),
      w('new'),
      w('guidances'),
      p('.'),
    ],
    criticNote: 'Source [2] reports "incremental adjustments," not a significant shift.',
    confidence: 73,
  },
  {
    query: 'How is the GLP-1 market shifting in 2026?',
    sources: [
      { title: 'NEJM — late-2025 meta-review', credibility: 96 },
      { title: 'Nature Medicine, Jan 2026', credibility: 93 },
      { title: 'Pharma Q1 earnings (Lilly, NVO)', credibility: 84 },
      { title: 'Endpoints News, weekly', credibility: 79 },
    ],
    draft: [
      w('Oral'),
      w('GLP-1'),
      w('candidates'),
      w('from'),
      w('Lilly'),
      c(1),
      w('and'),
      w('Pfizer'),
      c(2),
      w('are'),
      w('tracking'),
      w('toward'),
      w('late-2026'),
      w('approval'),
      p(','),
      w('while'),
      w('supply'),
      w('constraints'),
      w('have', true),
      w('eased', true),
      c(3),
      w('across'),
      w('major'),
      w('markets'),
      p('.'),
    ],
    criticNote: 'Source [3] limits easing to North America; EU and APAC still constrained.',
    confidence: 68,
  },
  {
    query: 'Where is venture capital flowing in CEE this year?',
    sources: [
      { title: 'Dealroom — CEE H1 2026', credibility: 92 },
      { title: 'Atomico — State of European Tech', credibility: 90 },
      { title: 'Crunchbase, last 90 days', credibility: 87 },
      { title: 'Sifted weekly digest', credibility: 75 },
    ],
    draft: [
      w('Romanian'),
      w('fintech'),
      c(1),
      w('and'),
      w('Polish'),
      w('climate-tech'),
      c(2),
      w('absorbed'),
      w('61%'),
      w('of'),
      w('CEE'),
      w('Series-A'),
      c(3),
      w('capital'),
      w('in'),
      w('H1'),
      w('2026'),
      p(','),
      w('with'),
      w('a'),
      w('marked', true),
      w('pull-back', true),
      c(4),
      w('from'),
      w('late-stage'),
      w('rounds'),
      p('.'),
    ],
    criticNote: 'Source [4] is a sample of n=22 — "marked" overstates the signal.',
    confidence: 64,
  },
  {
    query: 'What is the state of Asia–Europe shipping?',
    sources: [
      { title: "Lloyd's List — Red Sea monitor", credibility: 95 },
      { title: 'MarineTraffic API, Apr 2026', credibility: 91 },
      { title: 'WTO trade flow monitor', credibility: 87 },
      { title: 'Drewry composite index', credibility: 85 },
    ],
    draft: [
      w('Red'),
      w('Sea'),
      w('transits'),
      w('remain'),
      w('60%'),
      w('below'),
      c(1),
      w('pre-2024'),
      w('levels'),
      c(2),
      p(','),
      w('pushing'),
      w('Asia–Europe'),
      w('spot'),
      w('rates'),
      w('to'),
      w('a'),
      w('sustained', true),
      c(3),
      w('$4,200/FEU'),
      w('through'),
      w('April'),
      p('.'),
    ],
    criticNote: 'Source [3] shows rates dropped 12% week-on-week — "sustained" is unsupported.',
    confidence: 71,
  },
]
