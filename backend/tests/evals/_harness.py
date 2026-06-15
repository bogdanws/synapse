"""Judge harness: EvalConfig, JudgeScore, judge(), and rubric strings.

`os.environ` reads here are intentional — this module is test-only.
App configuration always goes through `app.config.get_settings()`.
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.services.llm import build_chat_model, invoke_structured_with_retry

_log = structlog.get_logger(__name__)

_DEFAULT_JUDGE_MODEL = "openai/gpt-5.1"
_DEFAULT_AGENT_MODEL = "openai/gpt-4o-mini"


class EvalConfig(BaseModel):
    """Runtime configuration for a single eval run, read from environment."""

    judge_model: str
    scout_models: list[str]
    scribe_models: list[str]
    critic_models: list[str]


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return [default]
    return [m.strip() for m in raw.split(",") if m.strip()]


def load_eval_config() -> EvalConfig:
    """Read eval config from environment variables.

    Empty or absent vars fall back to one cheap default model so a bare
    `pytest -m agent_eval` costs as little as possible.
    """
    judge = os.environ.get("EVAL_JUDGE_MODEL", "").strip() or _DEFAULT_JUDGE_MODEL
    cfg = EvalConfig(
        judge_model=judge,
        scout_models=_csv_env("EVAL_SCOUT_MODELS", _DEFAULT_AGENT_MODEL),
        scribe_models=_csv_env("EVAL_SCRIBE_MODELS", _DEFAULT_AGENT_MODEL),
        critic_models=_csv_env("EVAL_CRITIC_MODELS", _DEFAULT_AGENT_MODEL),
    )
    for agent, model_list in (
        ("scout", cfg.scout_models),
        ("scribe", cfg.scribe_models),
        ("critic", cfg.critic_models),
    ):
        for m in model_list:
            if m == cfg.judge_model:
                _log.warning(
                    "eval_judge_candidate_collision",
                    agent=agent,
                    model=m,
                    detail="judge and candidate are the same model; self-preference bias likely",
                )
    return cfg


class JudgeScore(BaseModel):
    """Structured output from one judge call.

    `reasoning` comes first so the model emits its chain-of-thought before
    committing to a score — this ordering consistently improves calibration
    when using structured JSON output with language models.
    """

    reasoning: str
    score: int = Field(ge=1, le=5)


# ---- Rubric constants -------------------------------------------------------
# One rubric per metric family. Each describes the 1-5 anchors and asks the
# model for reasoning-then-score in JSON. Keeping them as module constants
# makes them easy to review and version alongside the fixture data.

RUBRIC_SEARCH_QUERY_QUALITY = """\
You are an expert research methodologist evaluating search query quality.

Rate the sub-questions generated from the given research topic on a 1-5 scale:

1 — Very poor: vague, highly redundant, or off-topic; few would produce useful search results.
2 — Below average: some focused questions but many are too broad or overlapping.
3 — Acceptable: cover the main angles with minor redundancy or vagueness.
4 — Good: distinct, specific, and together cover the topic comprehensively.
5 — Excellent: mutually distinct, highly searchable, specific, and provide comprehensive coverage.

Consider: coverage of the topic, mutual distinctness, searchability, and specificity.

Respond with JSON: {"reasoning": "<2-3 sentences>", "score": <integer 1-5>}
"""

RUBRIC_COHERENCE = """\
You are an expert editor evaluating research report coherence.

Rate the coherence and readability of the report on a 1-5 scale:

1 — Very poor: disorganised, repetitive, or hard to follow.
2 — Below average: some logical flow but significant redundancy or abrupt transitions.
3 — Acceptable: mostly readable with minor coherence issues.
4 — Good: clear logical progression, minimal redundancy, smooth transitions.
5 — Excellent: highly readable, well-organised, no redundancy, excellent flow.

Respond with JSON: {"reasoning": "<2-3 sentences>", "score": <integer 1-5>}
"""

RUBRIC_FACTUAL_ACCURACY = """\
You are an expert fact-checker evaluating whether a research report's claims are supported by the provided sources.

Rate the factual accuracy of the report relative to the provided source snippets on a 1-5 scale:

1 — Very poor: major claims contradict or are not supported by the sources.
2 — Below average: several claims are unsupported or contradict sources.
3 — Acceptable: most claims are supported; a few unsupported statements present.
4 — Good: nearly all claims are supported by the sources; only minor gaps.
5 — Excellent: all claims are well-supported by the provided sources with no contradictions.

Only judge claims against the provided source snippets — do not apply outside knowledge.

Respond with JSON: {"reasoning": "<2-3 sentences>", "score": <integer 1-5>}
"""

RUBRIC_STRUCTURE_QUALITY = """\
You are an expert research editor evaluating report structure.

Rate the structural quality of the research report on a 1-5 scale:

1 — Very poor: no coherent structure; missing summary or sections; headings are uninformative.
2 — Below average: summary or section structure present but weak; fewer than 3 or more than 6 sections; poor headings.
3 — Acceptable: summary present, 3-6 sections with reasonable headings and ordering.
4 — Good: well-structured with a clear summary, 3-6 sections, descriptive headings, sensible ordering.
5 — Excellent: exemplary structure; compelling summary, ideal section count, precise headings, optimal ordering.

Respond with JSON: {"reasoning": "<2-3 sentences>", "score": <integer 1-5>}
"""

RUBRIC_RATIONALE_QUALITY = """\
You are an expert fact-checker evaluating the quality of fact-checking rationales.

Rate whether the fact-checker's rationales correctly justify their verdicts against the provided sources on a 1-5 scale:

1 — Very poor: rationales are absent, circular, or clearly wrong given the sources.
2 — Below average: rationales partially explain verdicts but miss key evidence or are misleading.
3 — Acceptable: rationales generally justify verdicts with minor gaps or imprecision.
4 — Good: rationales clearly cite relevant source evidence and correctly justify each verdict.
5 — Excellent: rationales are precise, cite specific evidence, and perfectly justify each verdict.

Respond with JSON: {"reasoning": "<2-3 sentences>", "score": <integer 1-5>}
"""


async def judge(*, judge_model: str, rubric: str, content: str) -> JudgeScore:
    """Single LLM-as-judge call returning a structured 1-5 score.

    Uses temperature=0 for maximum consistency across runs.
    `rubric` is the system message describing the 1-5 anchors and asking for
    reasoning-then-score. `content` is the material to grade plus any reference.
    Routed through `invoke_structured_with_retry` so the judge benefits from
    the same retry/repair path as the agents.
    """
    chat = build_chat_model(judge_model, temperature=0.0).with_structured_output(
        JudgeScore,
        method="json_mode",
        include_raw=True,
    )
    messages: list[Any] = [
        {"role": "system", "content": rubric},
        {"role": "user", "content": content},
    ]

    def _validate(parsed: JudgeScore) -> None:
        if not 1 <= parsed.score <= 5:
            msg = f"score {parsed.score} is outside [1, 5]"
            raise ValueError(msg)

    return await invoke_structured_with_retry(
        chat,
        messages,
        validate=_validate,
        retry_feedback=lambda err: (
            f"Invalid response: {err}. "
            'Reply with JSON: {"reasoning": "<your reasoning>", "score": <integer 1-5>}'
        ),
        max_retries=1,
        log_event="eval_judge_failed",
        log=_log,
    )
