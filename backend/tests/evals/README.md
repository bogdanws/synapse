# Agent Evals

LLM-as-judge evaluations for Scout, Scribe, and Critic. Slow, non-deterministic,
require API keys. Excluded from default `pytest` runs (see `pyproject.toml`'s
`addopts = "-m 'not agent_eval'"`).

Run on demand:

```bash
uv run pytest tests/evals/ -m agent_eval
uv run pytest tests/evals/ -m agent_eval -k scout
```

Each test must be marked `@pytest.mark.agent_eval`.
