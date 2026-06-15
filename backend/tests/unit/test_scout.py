"""Unit tests for `ScoutAgent` and the `run_scout` LangGraph node."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx

from app.agents.scout import ScoutAgent, ScoutValidationError, _canonical_url, _RawSource
from app.agents.scout_graph import (
    _MAX_MERGED_SEED_SOURCES,
    _MAX_SEED_SOURCES,
    ScoutOutput,
    run_scout,
)
from app.models.events import (
    ProgressEvent,
    ScoutComplete,
    SourceFound,
    SourceScored,
    SubQuestionsGenerated,
)
from app.models.research import Source
from app.services.llm import OPENROUTER_BASE_URL

# ---- helpers ---------------------------------------------------------------


def _openrouter_completion(json_content: str) -> dict[str, Any]:
    """Build a chat-completion response carrying `json_content` as the assistant message body.

    `with_structured_output(method="json_mode")` parses `choices[0].message.content` as JSON, so this minimal shape is enough to drive the langchain-openai client without function-calling.
    """
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json_content},
                "finish_reason": "stop",
            }
        ],
    }


def _raw(url: str, *, title: str = "T", content: str | None = "body text here") -> _RawSource:
    return _RawSource(
        url=url,
        title=title,
        author=None,
        published_at=None,
        snippet=(content or "")[:200],
        content=content,
    )


# ---- canonicalisation ------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("https://example.com/x", "https://example.com/x/"),
        ("https://Example.com/x", "https://example.com/x"),
        ("https://example.com/x#frag", "https://example.com/x"),
    ],
)
def test_canonical_url_treats_equivalents_as_equal(a: str, b: str) -> None:
    assert _canonical_url(a) == _canonical_url(b)


def test_canonical_url_preserves_query_strings() -> None:
    # Distinct articles often live behind the same path with different query
    # strings (paginated archives, doi resolvers, etc.). Stripping queries
    # would over-merge them.
    assert _canonical_url("https://example.com/article?id=1") != _canonical_url(
        "https://example.com/article?id=2"
    )


# ---- decompose -------------------------------------------------------------


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_decompose_returns_parsed_sub_questions(
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_openrouter_completion(
                '{"sub_questions": ["What is X?", "Why does X matter?", "How does X work?"]}'
            ),
        )
    )
    agent = ScoutAgent(model="test/model", search_client=_DummySearchClient([]))
    result = await agent.decompose("Topic")
    assert result == ["What is X?", "Why does X matter?", "How does X work?"]


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_decompose_rejects_too_few_sub_questions(
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_openrouter_completion('{"sub_questions": ["only one"]}'),
        )
    )
    agent = ScoutAgent(model="test/model", search_client=_DummySearchClient([]))
    # Pydantic's min_length=3 inside _SubQuestions makes the parsed shape
    # invalid; after the retry exhausts, decompose should surface a typed
    # ScoutValidationError rather than letting a generic langchain parser
    # exception bubble up.
    with pytest.raises(ScoutValidationError, match="failed to produce"):
        await agent.decompose("Topic")


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_decompose_retries_on_empty_response(
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty assistant body crashed the whole pipeline before this fix.

    With `include_raw=True` the parser returns `parsed=None` instead of raising,
    and the retry loop replays the (empty) prior turn back to the model along
    with a corrective user message.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    good = _openrouter_completion(
        '{"sub_questions": ["What is X?", "Why does X matter?", "How does X work?"]}'
    )
    route = respx_mock.post("/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=_openrouter_completion("")),  # empty body
            httpx.Response(200, json=good),
        ]
    )
    agent = ScoutAgent(model="test/model", search_client=_DummySearchClient([]))
    result = await agent.decompose("Topic")
    assert route.call_count == 2
    assert result == ["What is X?", "Why does X matter?", "How does X work?"]

    import json as _json

    second_request = route.calls[1].request
    body = _json.loads(second_request.content)
    roles = [m["role"] for m in body["messages"]]
    # system, original user, assistant(empty), corrective user.
    assert roles == ["system", "user", "assistant", "user"], roles
    assert body["messages"][-2]["content"] == ""
    assert "failed validation" in body["messages"][-1]["content"]


# ---- search ----------------------------------------------------------------


class _DummySearchClient:
    """Stand-in for ExaSearchClient that returns a canned list."""

    def __init__(self, results: list[Any]) -> None:
        self._results = results

    async def search(self, query: str, *, num_results: int = 5) -> list[Any]:
        return list(self._results)


async def test_search_uses_trafilatura_when_exa_text_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents import scout as scout_module
    from app.services.search import ExaResult

    fetched: list[str] = []

    async def fake_fetch(url: str, *, timeout: float = 15.0) -> str | None:
        fetched.append(url)
        return "fallback body"

    monkeypatch.setattr(scout_module, "fetch_article_text", fake_fetch)

    exa = _DummySearchClient(
        [
            ExaResult.model_validate(
                {
                    "url": "https://example.com/no-text",
                    "title": "No Text",
                    "text": None,
                }
            ),
            ExaResult.model_validate(
                {
                    "url": "https://example.com/has-text",
                    "title": "Has Text",
                    "text": "exa supplied body",
                }
            ),
        ]
    )
    agent = ScoutAgent(model="test/model", search_client=exa)  # type: ignore[arg-type]
    raw = await agent.search("q")

    assert len(raw) == 2
    assert fetched == ["https://example.com/no-text"]
    assert raw[0].content == "fallback body"
    assert raw[1].content == "exa supplied body"


# ---- deduplicate -----------------------------------------------------------


async def test_deduplicate_collapses_canonical_duplicates() -> None:
    agent = ScoutAgent(model="test/model", search_client=_DummySearchClient([]))  # type: ignore[arg-type]
    deduped = await agent.deduplicate(
        [
            _raw("https://example.com/a"),
            _raw("https://example.com/a/"),
            _raw("https://Example.com/a#section"),
            _raw("https://example.com/b"),
        ]
    )
    assert [s.url for s in deduped] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


# ---- score -----------------------------------------------------------------


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_score_combines_domain_prior_with_llm_judgement(
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    respx_mock.post("/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_openrouter_completion(
                '{"ratings": ['
                '{"index": 0, "relevance": 0.8, "credibility_llm": 1.0},'
                '{"index": 1, "relevance": 0.5, "credibility_llm": 0.5}'
                "]}"
            ),
        )
    )
    agent = ScoutAgent(model="test/model", search_client=_DummySearchClient([]))  # type: ignore[arg-type]
    scored = await agent.score(
        "topic",
        [
            _raw("https://www.nature.com/articles/x"),  # prior 0.95
            _raw("https://random-blog.example/post"),  # default prior 0.55
        ],
    )

    assert len(scored) == 2
    assert scored[0].id == "s1"
    assert scored[1].id == "s2"
    # nature * 1.0 ≈ 0.95
    assert scored[0].credibility == pytest.approx(0.95, abs=1e-3)
    # default 0.55 * 0.5 = 0.275
    assert scored[1].credibility == pytest.approx(0.275, abs=1e-3)
    assert scored[0].relevance == pytest.approx(0.8)
    assert scored[1].relevance == pytest.approx(0.5)


@pytest.mark.respx(base_url=OPENROUTER_BASE_URL)
async def test_score_falls_back_to_neutral_when_llm_call_fails(
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    respx_mock.post("/chat/completions").mock(return_value=httpx.Response(500))
    agent = ScoutAgent(model="test/model", search_client=_DummySearchClient([]))  # type: ignore[arg-type]
    scored = await agent.score(
        "topic",
        [_raw("https://www.nature.com/articles/x")],
    )
    # Soft failure: prior alone (≈ 0.95 * 1.0 default), neutral relevance 0.5.
    assert scored[0].relevance == pytest.approx(0.5)
    assert scored[0].credibility == pytest.approx(0.95, abs=1e-3)


# ---- run_scout (graph node) ------------------------------------------------


class _StaticAgent:
    """Stub that records inputs and returns canned outputs.

    Lets us test the node's event-emission contract without exercising the LLM stack again — those code paths are covered by the agent-level tests above.
    """

    def __init__(
        self,
        sub_questions: list[str],
        search_results: dict[str, list[_RawSource]],
        scored: list[Source],
    ) -> None:
        self._sub_questions = sub_questions
        self._search_results = search_results
        self._scored = scored
        self.search_calls: list[str] = []

    async def decompose(self, topic: str) -> list[str]:
        return self._sub_questions

    async def search(self, query: str) -> list[_RawSource]:
        self.search_calls.append(query)
        return self._search_results.get(query, [])

    async def deduplicate(self, sources: list[_RawSource]) -> list[_RawSource]:
        # Trivial: rely on URL identity.
        seen: set[str] = set()
        out: list[_RawSource] = []
        for s in sources:
            if s.url in seen:
                continue
            seen.add(s.url)
            out.append(s)
        return out

    async def score(self, topic: str, sources: list[_RawSource]) -> list[Source]:
        return list(self._scored)


async def test_run_scout_emits_lifecycle_events_in_order() -> None:
    job_id = uuid4()
    sources = [
        Source(
            id="s1",
            url="https://example.com/a",  # type: ignore[arg-type]
            title="A",
            credibility=0.7,
            relevance=0.9,
            snippet="...",
            published_at=datetime.now(UTC),
        ),
        Source(
            id="s2",
            url="https://example.com/b",  # type: ignore[arg-type]
            title="B",
            credibility=0.4,
            relevance=0.6,
            snippet="...",
        ),
    ]
    agent = _StaticAgent(
        sub_questions=["q1", "q2"],
        search_results={
            "q1": [_raw("https://example.com/a")],
            "q2": [_raw("https://example.com/b")],
        },
        scored=sources,
    )

    captured: list[ProgressEvent] = []

    async def capture(event: ProgressEvent) -> None:
        captured.append(event)

    output = await run_scout(
        job_id=job_id,
        topic="topic",
        agent=agent,  # type: ignore[arg-type]
        publish=capture,
    )

    assert isinstance(output, ScoutOutput)
    assert output.sub_questions == ["q1", "q2"]
    assert [s.id for s in output.sources] == ["s1", "s2"]

    # First event is decomposition, last is completion.
    assert isinstance(captured[0], SubQuestionsGenerated)
    assert captured[0].sub_questions == ["q1", "q2"]
    assert isinstance(captured[-1], ScoutComplete)
    assert captured[-1].source_count == 2

    # SourceFound events come before any SourceScored — frontend renders cards
    # before scores arrive.
    found_indices = [i for i, e in enumerate(captured) if isinstance(e, SourceFound)]
    scored_indices = [i for i, e in enumerate(captured) if isinstance(e, SourceScored)]
    assert found_indices and scored_indices
    assert max(found_indices) < min(scored_indices)

    # SourceFound payloads carry placeholder zeros; the scores live in
    # the SourceScored events.
    for ev in captured:
        if isinstance(ev, SourceFound):
            assert ev.source.credibility == 0.0
            assert ev.source.relevance == 0.0
        if isinstance(ev, SourceScored):
            assert ev.credibility > 0
            assert ev.relevance > 0


async def test_run_scout_continues_when_one_sub_question_search_fails() -> None:
    """A failed Exa call for one sub-question should not poison the rest of the run."""
    job_id = uuid4()
    sources = [
        Source(
            id="s1",
            url="https://example.com/a",  # type: ignore[arg-type]
            title="A",
            credibility=0.5,
            relevance=0.5,
            snippet="...",
        )
    ]

    class _FlakyAgent(_StaticAgent):
        async def search(self, query: str) -> list[_RawSource]:
            if query == "q2":
                raise RuntimeError("Exa transient failure")
            return await super().search(query)

    agent = _FlakyAgent(
        sub_questions=["q1", "q2"],
        search_results={"q1": [_raw("https://example.com/a")]},
        scored=sources,
    )

    captured: list[ProgressEvent] = []

    output = await run_scout(
        job_id=job_id,
        topic="topic",
        agent=agent,  # type: ignore[arg-type]
        publish=lambda e: _record(captured, e),
    )

    assert len(output.sources) == 1


class _CapturingAgent(_StaticAgent):
    """`_StaticAgent` that records the sources handed to `score`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.scored_input: list[_RawSource] = []

    async def score(self, topic: str, sources: list[_RawSource]) -> list[Source]:
        self.scored_input = list(sources)
        return await super().score(topic, sources)


def _seed(url: str, *, credibility: float, relevance: float, snippet: str = "seed") -> Source:
    return Source(
        id="s1",
        url=url,  # type: ignore[arg-type]
        title=url,
        credibility=credibility,
        relevance=relevance,
        snippet=snippet,
    )


async def test_run_scout_reuses_parent_sources_without_rescoring() -> None:
    """A follow-up keeps the parent's sources at their stored scores and only scores fresh hits.

    Seeds skip the scoring LLM (only their snippet is persisted, so re-judging would
    rate them on less material than the full-bodied fresh hits). A fresh hit that
    rediscovers a seed URL is dropped in favour of the parent copy, and the merged set
    is re-indexed into one clean citation id space (seeds first, then fresh).
    """
    job_id = uuid4()
    seed = [_seed("https://parent.example/a", credibility=0.6, relevance=0.7, snippet="parent")]
    fresh_scored = [
        Source(
            id="s1",
            url="https://new.example/b",  # type: ignore[arg-type]
            title="New B",
            credibility=0.5,
            relevance=0.8,
            snippet="...",
        ),
    ]
    agent = _CapturingAgent(
        sub_questions=["the follow-up question"],
        search_results={
            "the follow-up question": [
                _raw("https://parent.example/a", title="dup-from-search"),
                _raw("https://new.example/b", title="New B"),
            ]
        },
        scored=fresh_scored,
    )

    captured: list[ProgressEvent] = []
    output = await run_scout(
        job_id=job_id,
        topic="the follow-up question",
        agent=agent,  # type: ignore[arg-type]
        publish=lambda e: _record(captured, e),
        sub_questions_override=["the follow-up question"],
        seed_sources=seed,
    )

    # Only the fresh, non-colliding hit reaches the scorer; the seed is not re-judged
    # and the search-side duplicate of the seed URL is dropped.
    assert [r.url for r in agent.scored_input] == ["https://new.example/b"]

    assert [str(s.url) for s in output.sources] == [
        "https://parent.example/a",
        "https://new.example/b",
    ]
    # Re-indexed into a fresh, unique id space.
    assert [s.id for s in output.sources] == ["s1", "s2"]
    # The seed kept its parent-assigned score and snippet verbatim.
    seed_out = output.sources[0]
    assert (seed_out.credibility, seed_out.relevance) == (0.6, 0.7)
    assert seed_out.snippet == "parent"


async def test_run_scout_caps_seed_sources() -> None:
    """Only the strongest `_MAX_SEED_SOURCES` parent sources are carried into a follow-up."""
    job_id = uuid4()
    # Distinct, descending scores so the cap boundary is unambiguous.
    seeds = [
        _seed(f"https://parent.example/{i}", credibility=1.0, relevance=1.0 - i * 0.01)
        for i in range(_MAX_SEED_SOURCES + 5)
    ]
    agent = _StaticAgent(
        sub_questions=["q"],
        search_results={"q": []},
        scored=[],
    )

    output = await run_scout(
        job_id=job_id,
        topic="q",
        agent=agent,  # type: ignore[arg-type]
        publish=lambda e: _record([], e),
        sub_questions_override=["q"],
        seed_sources=seeds,
    )

    assert len(output.sources) == _MAX_SEED_SOURCES
    kept = {str(s.url) for s in output.sources}
    # The five weakest seeds are dropped.
    for i in range(_MAX_SEED_SOURCES, _MAX_SEED_SOURCES + 5):
        assert f"https://parent.example/{i}" not in kept


async def test_run_scout_caps_merged_seed_set() -> None:
    """The combined seed+fresh set a follow-up emits is bounded, so chains can't grow unbounded."""
    job_id = uuid4()
    seeds = [
        _seed(f"https://parent.example/{i}", credibility=0.5, relevance=0.5)
        for i in range(_MAX_MERGED_SEED_SOURCES - 2)
    ]
    fresh_scored = [
        Source(
            id="s1",
            url=f"https://new.example/{i}",  # type: ignore[arg-type]
            title=f"new {i}",
            credibility=0.9,
            relevance=0.9,
            snippet="...",
        )
        for i in range(5)
    ]
    agent = _StaticAgent(
        sub_questions=["q"],
        search_results={"q": [_raw(f"https://new.example/{i}") for i in range(5)]},
        scored=fresh_scored,
    )

    output = await run_scout(
        job_id=job_id,
        topic="q",
        agent=agent,  # type: ignore[arg-type]
        publish=lambda e: _record([], e),
        sub_questions_override=["q"],
        seed_sources=seeds,
    )

    assert len(output.sources) == _MAX_MERGED_SEED_SOURCES
    # The high-scoring fresh hits all survive the cap; the weakest seeds are dropped.
    kept = {str(s.url) for s in output.sources}
    for i in range(5):
        assert f"https://new.example/{i}" in kept


async def _record(out: list[ProgressEvent], event: ProgressEvent) -> None:
    out.append(event)
