"""Scout eval: query-decomposition quality, judged with no external dependencies.

Parametrised over EVAL_SCOUT_MODELS × scout_topics.json. Exercises only
`ScoutAgent.decompose` — the model's genuine reasoning step — and judges the
resulting sub-questions. No Exa/search calls are made: source retrieval and
scoring are dominated by Exa's ranking, so scoring them measures the search API
more than the model under test.

A test only fails on infrastructure errors; decomposition-quality failures are
recorded, not raised.
"""

from __future__ import annotations

import httpx
import pytest

from app.agents.scout import ScoutAgent, ScoutValidationError
from app.services.search import ExaSearchClient
from tests.evals._harness import (
    RUBRIC_SEARCH_QUERY_QUALITY,
    EvalConfig,
    judge,
    load_eval_config,
)
from tests.evals._loaders import ScoutTopic, load_scout_topics
from tests.evals._reporting import EvalRecorder

_cfg = load_eval_config()
_TOPICS = load_scout_topics()
_PARAMS = [(m, t) for m in _cfg.scout_models for t in _TOPICS]


@pytest.mark.agent_eval
@pytest.mark.parametrize(
    "model,topic_obj",
    _PARAMS,
    ids=[f"{m.split('/')[-1]}__{t.id}" for m, t in _PARAMS],
)
async def test_scout_quality(
    model: str,
    topic_obj: ScoutTopic,
    eval_config: EvalConfig,
    eval_recorder: EvalRecorder,
    http_client: httpx.AsyncClient,
) -> None:
    # ScoutAgent's constructor requires a search client, but `decompose` never
    # touches it. Wire an unauthenticated client to the managed transport so no
    # network call is possible and no EXA_API_KEY is needed.
    agent = ScoutAgent(model, search_client=ExaSearchClient(api_key="", http_client=http_client))
    try:
        sub_questions = await agent.decompose(topic_obj.topic)
    except ScoutValidationError as exc:
        # Candidate-quality failure (decompose never produced a usable list),
        # not infrastructure.
        eval_recorder.record("scout", model, topic_obj.id, "output_valid", 0.0, str(exc))
        eval_recorder.record_output(
            "scout", model, topic_obj.id, f"**SCOUT DECOMPOSE FAILED after retries:**\n\n{exc}"
        )
        return
    eval_recorder.record("scout", model, topic_obj.id, "output_valid", 1.0)
    eval_recorder.record_output("scout", model, topic_obj.id, _format_scout(sub_questions))

    sub_q_block = "\n".join(f"- {q}" for q in sub_questions)
    sq_score = await judge(
        judge_model=eval_config.judge_model,
        rubric=RUBRIC_SEARCH_QUERY_QUALITY,
        content=f"Topic: {topic_obj.topic}\n\nSub-questions:\n{sub_q_block}",
    )
    eval_recorder.record(
        "scout",
        model,
        topic_obj.id,
        "search_query_quality",
        sq_score.score,
        sq_score.reasoning,
    )


def _format_scout(sub_questions: list[str]) -> str:
    """Render Scout's decomposition as Markdown for manual review."""
    parts = ["**Sub-questions:**"]
    parts.extend(f"- {q}" for q in sub_questions)
    return "\n".join(parts)
