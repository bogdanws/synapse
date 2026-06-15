import type { VerifiedReport } from '../types/api'

/*
 * Hand-authored report used by the public `/sample-report` route and the
 * landing page's "Read a sample report" CTA. It is intentionally static (not
 * fetched) so the showcase renders identically in dev, prod, and on poor
 * connections, and so it can demonstrate the full feature surface without a
 * live pipeline run: claims of every verdict, footnotes, per-section
 * confidence, source disagreements, and follow-up questions.
 *
 * The body markup mirrors what Scribe emits: verifiable claims wrapped in
 * `<span data-claim="secN.cM">…</span>` and citations as `[^sN]`. Verdicts in
 * `claim_flags` must reference those claim ids; `source_ids` in
 * `contradictions` must reference >= 2 distinct, known `Source.id` values —
 * the same invariants `backend/app/services/validation.py` enforces.
 */

const GENERATED_AT = '2026-04-22T09:30:00Z'

export const SAMPLE_REPORT: VerifiedReport = {
  job: {
    id: 'sample00-0000-0000-0000-000000000000',
    topic: 'Are small modular reactors ready to scale in 2026?',
    language: 'en',
    depth: 'standard',
    models: {
      scout: 'openai/gpt-4o',
      scribe: 'anthropic/claude-3.7-sonnet',
      critic: 'openai/gpt-4o',
    },
    status: 'completed',
    progress: 1.0,
    created_at: GENERATED_AT,
    updated_at: GENERATED_AT,
    completed_at: GENERATED_AT,
  },
  report: {
    id: 'sample-report-001',
    job_id: 'sample00-0000-0000-0000-000000000000',
    topic: 'Are small modular reactors ready to scale in 2026?',
    title: 'Small modular reactors: a decade of promise meets the cost curve',
    summary_md:
      'Small modular reactors (SMRs) have cleared their first regulatory milestones, but the case for near-term scale rests on cost assumptions that the underlying sources do not agree on. Designs are real and licensable; the economics — and the 2027 deployment timelines built on them — remain contested.',
    sections: [
      {
        id: 'sec1',
        heading: 'The design promise',
        body_md:
          'SMRs are reactors that <span data-claim="sec1.c1">generate under 300 MWe and are assembled from factory-built modules rather than poured on site</span>.[^s1] Proponents argue this shifts nuclear from bespoke megaprojects to a manufacturing problem, which should compress both schedule and cost. On that basis several vendors now <span data-claim="sec1.c2">expect first commercial U.S. operation in 2027</span>.[^s2]',
        cited_source_ids: ['s1', 's2'],
      },
      {
        id: 'sec2',
        heading: 'Where the licensing actually stands',
        body_md:
          'NuScale\'s VOYGR design <span data-claim="sec2.c1">received U.S. Nuclear Regulatory Commission design certification in 2023</span>, the first SMR to do so.[^s3] That is a genuine milestone. It does not, however, support the further claim that the technology is <span data-claim="sec2.c2">already the cheapest source of grid power available today</span>.[^s2]',
        cited_source_ids: ['s2', 's3'],
      },
      {
        id: 'sec3',
        heading: 'The cost question nobody agrees on',
        body_md:
          'Cost is where the sources diverge most sharply. China\'s Linglong One is sometimes cited as proof of cheap output, with one figure putting it at <span data-claim="sec3.c1">$40/MWh at commercial operation</span>.[^s4] Independent analysis is far less optimistic, finding that <span data-claim="sec3.c2">SMR electricity is likely to remain meaningfully more expensive than utility-scale solar and onshore wind through at least 2030</span>.[^s5]',
        cited_source_ids: ['s4', 's5'],
      },
    ],
    sources: [
      {
        id: 's1',
        url: 'https://www.iaea.org/topics/small-modular-reactors',
        title: 'IAEA — Small Modular Reactors overview',
        author: 'International Atomic Energy Agency',
        published_at: '2025-11-03',
        credibility: 0.95,
        relevance: 0.9,
        snippet:
          'SMRs are advanced reactors with a power capacity of up to 300 MW(e), designed for factory assembly and modular deployment.',
      },
      {
        id: 's2',
        url: 'https://www.vendor-press-release.example.com/smr-2027',
        title: 'Vendor briefing: "Cheapest power on the grid by 2027"',
        author: 'SMR consortium press office',
        published_at: '2026-02-18',
        credibility: 0.52,
        relevance: 0.74,
        snippet:
          'The consortium projects first commercial operation in 2027 and positions SMR output as the lowest-cost grid power available.',
      },
      {
        id: 's3',
        url: 'https://www.nrc.gov/reactors/new-reactors/smr/nuscale.html',
        title: 'U.S. NRC — NuScale design certification record',
        author: 'U.S. Nuclear Regulatory Commission',
        published_at: '2023-02-21',
        credibility: 0.97,
        relevance: 0.86,
        snippet:
          'The NRC certified the NuScale small modular reactor design, the first SMR design certification issued in the United States.',
      },
      {
        id: 's4',
        url: 'https://www.world-nuclear-news.org/linglong-one',
        title: 'World Nuclear News — Linglong One progress report',
        author: 'World Nuclear News',
        published_at: '2026-01-09',
        credibility: 0.81,
        relevance: 0.7,
        snippet:
          'Construction milestones reported for the Linglong One demonstration unit, with commercial operation repeatedly rescheduled.',
      },
      {
        id: 's5',
        url: 'https://www.lazard.com/research-insights/levelized-cost-of-energy',
        title: 'Lazard — Levelized Cost of Energy analysis',
        author: 'Lazard',
        published_at: '2025-06-12',
        credibility: 0.91,
        relevance: 0.88,
        snippet:
          'Unsubsidised SMR cost estimates sit well above utility-scale solar and onshore wind on a levelized basis.',
      },
    ],
    contradictions: [
      {
        topic: 'First commercial operation date',
        positions: [
          {
            statement: 'First commercial operation arrives in 2027.',
            source_ids: ['s2'],
          },
          {
            statement:
              'A string of schedule slips pushes realistic commercial operation to 2030 or later.',
            source_ids: ['s4'],
          },
        ],
      },
      {
        topic: 'Cost of SMR electricity',
        positions: [
          {
            statement: 'Linglong One output is cited at roughly $40/MWh at commercial operation.',
            source_ids: ['s4'],
          },
          {
            statement:
              'Independent levelized-cost analysis finds SMR electricity remains 2–3× more expensive than utility-scale solar and wind.',
            source_ids: ['s5'],
          },
        ],
      },
    ],
    follow_ups: [
      'What is the realistic, risk-adjusted first-of-a-kind cost for a Western SMR once financing and delays are priced in?',
      'How much of the projected cost decline depends on order-book volumes that have not yet materialised?',
      'Which regulatory regimes outside the U.S. and China are on track to license SMR designs before 2030?',
    ],
    generated_at: GENERATED_AT,
    model: 'anthropic/claude-3.7-sonnet',
  },
  annotations: {
    id: 'sample-annotations-001',
    report_id: 'sample-report-001',
    section_confidence: [
      {
        section_id: 'sec1',
        score: 0.88,
        reasoning:
          'The definition is well-sourced to the IAEA; the 2027 timeline is vendor-stated and carries more uncertainty.',
      },
      {
        section_id: 'sec2',
        score: 0.72,
        reasoning:
          'Certification claim is verified against the NRC record. The "cheapest power" claim is promotional and unsupported by independent data.',
      },
      {
        section_id: 'sec3',
        score: 0.54,
        reasoning:
          'Primary cost figures come from sources that directly contradict each other; treat the headline numbers with caution.',
      },
    ],
    claim_flags: [
      {
        claim_id: 'sec1.c1',
        section_id: 'sec1',
        verdict: 'supported',
        rationale: 'Matches the IAEA definition of an SMR (≤300 MWe, factory-assembled modules).',
        supporting_source_ids: ['s1'],
      },
      {
        claim_id: 'sec1.c2',
        section_id: 'sec1',
        verdict: 'partially_supported',
        rationale:
          'A 2027 target is stated by the vendor, but no independent source corroborates the date and similar projects have slipped.',
        supporting_source_ids: ['s2'],
      },
      {
        claim_id: 'sec2.c1',
        section_id: 'sec2',
        verdict: 'supported',
        rationale: 'Confirmed by the NRC certification record for the NuScale design.',
        supporting_source_ids: ['s3'],
      },
      {
        claim_id: 'sec2.c2',
        section_id: 'sec2',
        verdict: 'unsupported',
        rationale:
          'No independent source supports "cheapest power available today"; the only basis is a vendor press release.',
        supporting_source_ids: [],
      },
      {
        claim_id: 'sec3.c1',
        section_id: 'sec3',
        verdict: 'contradicted',
        rationale:
          'The $40/MWh figure is contradicted by independent levelized-cost analysis placing SMR output far higher.',
        supporting_source_ids: ['s5'],
      },
      {
        claim_id: 'sec3.c2',
        section_id: 'sec3',
        verdict: 'supported',
        rationale:
          'Consistent with Lazard levelized-cost estimates for SMRs versus solar and wind.',
        supporting_source_ids: ['s5'],
      },
    ],
    overall_confidence: 0.71,
    model: 'openai/gpt-4o',
    generated_at: GENERATED_AT,
  },
}
