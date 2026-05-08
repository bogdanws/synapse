"""Scout — research agent.

Breaks a user topic into sub-questions, runs each sub-question through Exa, falls back to trafilatura when Exa returns no body text, deduplicates by URL, and produces a final list of `Source` records. Each source's credibility is the product of a domain-prior heuristic (`app.services.credibility`) and a per-source LLM rating; relevance comes from the same LLM pass.

The agent class is pure: it exposes async methods that take and return data. Event publishing and graph state lives in the LangGraph node wrapper (`app.agents.scout_graph`) so the agent stays trivially unit-testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

import structlog
from pydantic import BaseModel, Field

from app.models.research import Source
from app.services.credibility import domain_prior
from app.services.llm import (
    StructuredRetryError,
    build_chat_model,
    invoke_structured_with_retry,
)
from app.services.search import (
    ExaResult,
    ExaSearchClient,
    derive_snippet,
    fetch_article_text,
)

_log = structlog.get_logger(__name__)

# Bounds on Scout's output. Top-end caps protect against runaway LLMs producing 50 sub-questions; bottom-end ensures the model engages with the prompt.
_MIN_SUB_QUESTIONS = 3
_MAX_SUB_QUESTIONS = 7
_RESULTS_PER_QUESTION = 5

# One initial attempt plus this many retries when the decompose call returns malformed JSON or a sub-question list that violates the schema bounds. Mirrors the Scribe/Critic pattern; the retry replays the model's previous (bad) response back as an assistant turn so the model can see exactly what it produced.
_MAX_DECOMPOSE_RETRIES = 1


class ScoutValidationError(RuntimeError):
    """Raised when Scout cannot produce a usable sub-question list after all retries.

    Distinct from network errors: this means the model was reachable but its response was structurally unusable (empty body, non-JSON, wrong shape, or a list outside `[_MIN_SUB_QUESTIONS, _MAX_SUB_QUESTIONS]`).
    """


_DECOMPOSE_SYSTEM_PROMPT = (
    "You are a senior research analyst. Decompose a research topic into focused, "
    "mutually-distinct sub-questions whose answers together cover the topic. "
    "Each sub-question must be answerable from public sources and be specific "
    "enough to drive a targeted web search. Return strictly valid JSON matching "
    'the shape {"sub_questions": [string, ...]} with between '
    f"{_MIN_SUB_QUESTIONS} and {_MAX_SUB_QUESTIONS} items, no commentary, no markdown."
)

_SCORE_SYSTEM_PROMPT = (
    "You evaluate web sources for a research project. For each source, score:\n"
    "- `relevance` in [0, 1]: how directly the source addresses the topic;\n"
    "- `credibility_llm` in [0, 1]: how trustworthy the source seems on this "
    "topic (judging the author/publication, methodology cues in the snippet, "
    "and absence of obvious bias). Do NOT factor the domain reputation in — "
    "that is handled separately.\n"
    "Return strictly valid JSON of the form "
    '{"ratings": [{"index": int, "relevance": number, "credibility_llm": number}, ...]} '
    "with exactly one entry per source, in the same order, no commentary, no markdown."
)


@dataclass(slots=True)
class _RawSource:
    """Internal wide form for a source pre-scoring.

    Holds the full extracted body text (`content`) so the scoring LLM has more material to judge than the short snippet that ends up in `Source.snippet`.
    """

    url: str
    title: str
    author: str | None
    published_at: datetime | None
    snippet: str
    content: str | None


class _SubQuestions(BaseModel):
    sub_questions: list[str] = Field(
        min_length=_MIN_SUB_QUESTIONS,
        max_length=_MAX_SUB_QUESTIONS,
    )


class _SourceRating(BaseModel):
    index: int = Field(ge=0)
    relevance: float = Field(ge=0.0, le=1.0)
    credibility_llm: float = Field(ge=0.0, le=1.0)


class _SourceRatings(BaseModel):
    ratings: list[_SourceRating]


class ScoutAgent:
    """Pure logic; no event publishing.

    The constructor takes an explicit `ExaSearchClient` so tests can inject one wired to a respx-mocked transport, and so the orchestrator can share a single client across many topics in a single run.
    """

    def __init__(
        self,
        model: str,
        *,
        search_client: ExaSearchClient,
        results_per_question: int = _RESULTS_PER_QUESTION,
    ) -> None:
        self.model = model
        self._search = search_client
        self._results_per_question = results_per_question

    async def decompose(self, topic: str) -> list[str]:
        """Break a topic into 3-7 focused sub-questions.

        Routed through `invoke_structured_with_retry`, which is robust to the two failure modes we've seen in production: an empty response body (model returns `""`, which the JSON parser cannot decode) and a list that violates the schema bounds. Without that wrapper the langchain JSON parser raises `OutputParserException` mid-pipeline and the whole job dies.

        Raises `ScoutValidationError` if no attempt produces a usable list.
        """
        chat = build_chat_model(self.model).with_structured_output(
            _SubQuestions,
            method="json_mode",
            include_raw=True,
        )
        messages: list[Any] = [
            {"role": "system", "content": _DECOMPOSE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Topic: {topic}"},
        ]

        try:
            parsed = await invoke_structured_with_retry(
                chat,
                messages,
                validate=_validate_sub_questions,
                retry_feedback=_decompose_retry_feedback,
                max_retries=_MAX_DECOMPOSE_RETRIES,
                log_event="scout_decompose_failed",
                log=_log,
            )
        except StructuredRetryError as exc:
            msg = (
                f"scout failed to produce a valid sub-question list "
                f"after {exc.attempts} attempts: {exc.last_error}"
            )
            raise ScoutValidationError(msg) from exc

        return [q.strip() for q in parsed.sub_questions if q.strip()]

    async def search(self, query: str) -> list[_RawSource]:
        """Run a single Exa search; fall back to trafilatura on results without text."""
        results = await self._search.search(query, num_results=self._results_per_question)
        raw: list[_RawSource] = []
        for r in results:
            content = r.text
            if not content:
                content = await fetch_article_text(r.url)
            raw.append(_to_raw_source(r, content))
        return raw

    async def deduplicate(self, sources: list[_RawSource]) -> list[_RawSource]:
        """Remove duplicate URLs.

        Canonicalises by lower-casing the host and stripping the fragment + trailing slash.
        Query strings are preserved because they often disambiguate articles (paginated archives, doi resolvers, etc.).
        Order is preserved: the first occurrence wins because Exa already returns results in a relevance-ordered list.
        """
        seen: set[str] = set()
        out: list[_RawSource] = []
        for src in sources:
            key = _canonical_url(src.url)
            if key in seen:
                continue
            seen.add(key)
            out.append(src)
        return out

    async def score(self, topic: str, sources: list[_RawSource]) -> list[Source]:
        """Score relevance and credibility, then assign final short_ids and produce `Source` records.

        Final credibility is `domain_prior(url) * llm_credibility`. If the LLM rating call fails, we fall back to the prior alone so the pipeline still progresses with a usable but less-discerning score.
        """
        if not sources:
            return []

        ratings_by_index = await self._rate_via_llm(topic, sources)

        scored: list[Source] = []
        for i, src in enumerate(sources):
            prior = domain_prior(src.url)
            rating = ratings_by_index.get(i)
            relevance = rating.relevance if rating is not None else 0.5
            llm_cred = rating.credibility_llm if rating is not None else 1.0
            scored.append(
                Source(
                    id=f"s{i + 1}",
                    url=src.url,  # type: ignore[arg-type]
                    title=src.title or src.url,
                    author=src.author,
                    published_at=src.published_at,
                    credibility=round(prior * llm_cred, 4),
                    relevance=round(relevance, 4),
                    snippet=src.snippet,
                )
            )
        return scored

    async def _rate_via_llm(
        self, topic: str, sources: list[_RawSource]
    ) -> dict[int, _SourceRating]:
        """Single batched LLM call rating every source.

        Returns a mapping from input index → rating. Indices missing from the response are simply absent in the map; `score()` then falls back to neutral defaults for those entries.
        """
        chat = build_chat_model(self.model).with_structured_output(
            _SourceRatings,
            method="json_mode",
        )
        user_blob = "\n\n".join(
            f"[{i}] {src.title}\nURL: {src.url}\nSnippet: {derive_snippet(src.content, src.snippet)}"
            for i, src in enumerate(sources)
        )
        try:
            result = await chat.ainvoke(
                [
                    {"role": "system", "content": _SCORE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Topic: {topic}\n\nSources:\n{user_blob}"},
                ]
            )
        except Exception as exc:
            # Soft failure: the prior alone is still useful, and degrading gracefully here keeps a flaky model from sinking the whole job.
            _log.warning("scout_score_llm_failed", error=str(exc), source_count=len(sources))
            return {}

        if not isinstance(result, _SourceRatings):
            _log.warning("scout_score_unexpected_type", type=str(type(result)))
            return {}
        return {r.index: r for r in result.ratings if 0 <= r.index < len(sources)}


def _validate_sub_questions(parsed: _SubQuestions) -> None:
    """Validator passed to `invoke_structured_with_retry` for `decompose`.

    Pydantic's `min_length` / `max_length` already enforces the bounds, but stripping blank entries can drop the count below the minimum, which the helper would otherwise miss. Re-checking after the strip keeps the contract honest.
    """
    cleaned = [q.strip() for q in parsed.sub_questions if q.strip()]
    if not _MIN_SUB_QUESTIONS <= len(cleaned) <= _MAX_SUB_QUESTIONS:
        msg = (
            f"after stripping blanks, got {len(cleaned)} sub-questions; "
            f"need between {_MIN_SUB_QUESTIONS} and {_MAX_SUB_QUESTIONS}"
        )
        raise ValueError(msg)


def _decompose_retry_feedback(error: str) -> str:
    """Decompose retries re-state the schema verbatim because the failure mode we hit most often is the model emitting an empty body or commentary, not a near-miss the model can correct from a generic 'try again'."""
    return (
        f"Your previous response failed validation: {error}\n\n"
        "Reply with strictly valid JSON of the form "
        '{"sub_questions": [string, ...]} with between '
        f"{_MIN_SUB_QUESTIONS} and {_MAX_SUB_QUESTIONS} non-empty entries. "
        "No commentary, no markdown fence."
    )


def _to_raw_source(r: ExaResult, content: str | None) -> _RawSource:
    snippet = derive_snippet(content, fallback=r.title or r.url)
    return _RawSource(
        url=r.url,
        title=r.title or r.url,
        author=r.author,
        published_at=r.parsed_published_at,
        snippet=snippet,
        content=content,
    )


def _canonical_url(url: str) -> str:
    """Conservative URL canonicalisation for dedup.

    Lowercases host, drops fragment and trailing slash from the path, leaves query strings intact (they often distinguish distinct articles).
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/") or "/"
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))
