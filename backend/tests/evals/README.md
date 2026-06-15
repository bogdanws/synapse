# Agent Evals

LLM-as-judge evaluations for Scout, Scribe, and Critic. Slow, non-deterministic,
require real API keys. Excluded from default `pytest` runs; run on demand or via
the **Agent Evals** GitHub Actions workflow (`workflow_dispatch`).

## Quick start

```bash
cd backend
export OPENROUTER_API_KEY=...   # required: agent + judge calls

# Smoke-run Scribe with one cheap model and two cases (~5 judge calls, < $0.01):
export EVAL_JUDGE_MODEL=openai/gpt-4o-mini
export EVAL_SCRIBE_MODELS=openai/gpt-4o-mini
uv run pytest tests/evals/ -m agent_eval -k scribe -s

# Full model bake-off (real cost — run intentionally):
export EVAL_SCRIBE_MODELS="openai/gpt-4o-mini,openai/gpt-5.1,anthropic/claude-3.5-sonnet"
uv run pytest tests/evals/ -m agent_eval -k scribe -s
```

After a run, `tests/evals/results/` contains:
- `<UTC-timestamp>.json` — every raw metric row
- `<UTC-timestamp>.md` — leaderboard table per agent
- `<UTC-timestamp>_outputs.md` — full agent transcripts (sub-questions for
  Scout, the rendered report for Scribe, every verdict next to its ground-truth
  label for Critic) so you can manually verify *how the output actually looks*,
  not just the scores. Critic transcripts mark each claim where the model's flag
  disagrees with the label (`<-- MISMATCH`).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `EVAL_JUDGE_MODEL` | `openai/gpt-5.1` | OpenRouter model id for the LLM judge |
| `EVAL_SCOUT_MODELS` | `openai/gpt-4o-mini` | Comma-separated candidate models for Scout |
| `EVAL_SCRIBE_MODELS` | `openai/gpt-4o-mini` | Comma-separated candidate models for Scribe |
| `EVAL_CRITIC_MODELS` | `openai/gpt-4o-mini` | Comma-separated candidate models for Critic |

**Judge model choice:** use a model at least as capable as the agents under
test. `gpt-5.1` (default) is a strong reasoner at moderate cost. Never use
the same model as both judge and candidate — the harness warns when it detects
this to guard against self-preference bias.

**Cost:** defaults are one cheap model × 4 cases per agent. A full default run
is a few dozen API calls. Cost scales with `(#candidate models) × (#cases)`;
multiply by ~3 judge calls per Scribe case and ~1 per Critic case.

## Fixture coverage

Cases span four domains so a single model can be compared across topic types:
energy (grid storage), ML (LLM scaling/efficiency), genetics (CRISPR/Casgevy),
and pharma (semaglutide/SELECT). Snippets are grounded in real source text
pulled from Exa so the facts are checkable.

Critic cases embed *subtle* labeled falsehoods — number swaps (e.g. age 12 → 18),
entity swaps (e.g. Nobel Chemistry → Physiology/Medicine), and fabricated or
over-generalized stats — rather than blatant contradictions. These discriminate
precision/recall far better: a weak model tends to hedge with
`partially_supported` (counted as not-flagged, surfaced in `detail`) instead of
committing to `unsupported`/`contradicted`.

## Fixture formats

### `data/scout_topics.json`

Array of research topics. The Scout eval runs each topic through
`ScoutAgent.decompose` and judges the resulting sub-questions for query quality;
no sources are retrieved or scored, so the eval has no external dependencies.

```json
[
  {
    "id": "short_snake_case_id",
    "topic": "Full research topic string"
  }
]
```

### `data/scribe_cases.json`

Array of fixed-input cases (topic + sub-questions + pre-fetched sources).
`snippet` must contain enough verifiable fact for the factual-accuracy judge.

```json
[
  {
    "id": "short_snake_case_id",
    "topic": "...",
    "sub_questions": ["...", "..."],
    "sources": [
      {
        "id": "s1", "url": "https://...", "title": "...",
        "author": null, "published_at": null,
        "credibility": 0.9, "relevance": 0.9,
        "snippet": "verifiable factual sentence(s)"
      }
    ]
  }
]
```

### `data/critic_cases.json`

Array of pre-written reports with labeled claims. `"false"` labels are
inserted falsehoods the Critic should flag; `"supported"` labels are claims
the cited source actually supports.

The fixture must satisfy `validate_scribe_report()`:
- Section ids are `sec1`, `sec2`, ... sequential.
- Claim ids within each section are `secN.c1`, `secN.c2`, ... sequential.
- Every `[^sX]` footnote reference sits inside a `<span data-claim>` span.
- Every `sX` reference resolves to a source in the `sources` array.

```json
[
  {
    "id": "short_snake_case_id",
    "topic": "...", "title": "...", "summary_md": "...",
    "sources": [{"id": "s1", "url": "https://...", "title": "...",
                 "credibility": 0.9, "relevance": 0.9, "snippet": "..."}],
    "sections": [
      {"id": "sec1", "heading": "...",
       "body_md": "Text <span data-claim=\"sec1.c1\">claim[^s1]</span>."}
    ],
    "labels": {"sec1.c1": "supported"},
    "contradictions": [],
    "follow_ups": []
  }
]
```

## CI / GitHub Actions

Trigger via **Actions → Agent Evals → Run workflow**. Optional inputs:
- `agent`: `scout` / `scribe` / `critic` / `all` (default `all`)
- `judge_model`, `scout_models`, `scribe_models`, `critic_models`: override defaults

The workflow uploads `tests/evals/results/` as an artifact named `eval-results`;
download it from the run summary page to inspect leaderboard tables and raw rows.
