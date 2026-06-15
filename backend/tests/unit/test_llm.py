"""Unit tests for `invoke_structured_with_retry` in `app.services.llm`.

These tests exercise the helper in isolation against a stub `Runnable`, so we cover the three failure modes deterministically without depending on the langchain-openai / OpenAI SDK internals (which are exercised end-to-end through the agent tests). The transport-failure path in particular is hard to mock at the respx layer because the failure originates inside the OpenAI SDK's response parser, not the wire transport.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest
import structlog
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.services.llm import (
    StructuredRetryError,
    dated_system_prompt,
    invoke_structured_with_retry,
)


class _Schema(BaseModel):
    value: int


class _StubChat:
    """Minimal `Runnable`-shaped stub.

    Each invocation pops the next entry from `plays`. An exception in the list is raised; anything else is returned. Records every messages list it was called with so tests can assert on conversation evolution.
    """

    def __init__(self, plays: list[Any]) -> None:
        self._plays = list(plays)
        self.invocations: list[list[Any]] = []

    async def ainvoke(  # noqa: D401 - matches Runnable.ainvoke signature
        self, input: Any, config: Any = None, **kwargs: Any
    ) -> Any:
        # Snapshot the messages at call time so later mutations by the helper don't retroactively change what we recorded.
        self.invocations.append(list(input))
        play = self._plays.pop(0)
        if isinstance(play, BaseException):
            raise play
        return play


def _ok(value: int, *, content: str = "") -> dict[str, Any]:
    """Build the dict shape `with_structured_output(..., include_raw=True)` produces."""
    return {
        "raw": AIMessage(content=content or f'{{"value": {value}}}'),
        "parsed": _Schema(value=value),
        "parsing_error": None,
    }


def _bad_parse(*, content: str = "garbage") -> dict[str, Any]:
    return {
        "raw": AIMessage(content=content),
        "parsed": None,
        "parsing_error": ValueError("not JSON"),
    }


def _no_op_validator(_parsed: _Schema) -> None:
    return None


def _retry_feedback(error: str) -> str:
    return f"please fix: {error}"


def _stub_log() -> Any:
    return structlog.get_logger("test")


async def _invoke(
    chat: _StubChat,
    messages: list[Any],
    *,
    validate: Callable[[_Schema], None] = _no_op_validator,
    max_retries: int = 1,
) -> _Schema:
    return await invoke_structured_with_retry(
        cast(Runnable[Any, dict[str, Any]], chat),
        messages,
        validate=validate,
        retry_feedback=_retry_feedback,
        max_retries=max_retries,
        log_event="test_event",
        log=_stub_log(),
    )


# ---- happy path -----------------------------------------------------------


async def test_returns_parsed_on_first_success() -> None:
    chat = _StubChat([_ok(42)])
    result = await _invoke(chat, [{"role": "user", "content": "hi"}])
    assert result.value == 42
    assert len(chat.invocations) == 1


# ---- parse failure --------------------------------------------------------


async def test_replays_assistant_turn_on_parse_failure() -> None:
    chat = _StubChat([_bad_parse(content="not json"), _ok(7)])
    messages: list[Any] = [{"role": "user", "content": "hi"}]
    result = await _invoke(chat, messages)

    assert result.value == 7
    assert len(chat.invocations) == 2

    # Second invocation must include the bad assistant turn and a corrective user turn.
    second = chat.invocations[1]
    assert len(second) == 3
    assert isinstance(second[1], AIMessage)
    assert second[1].content == "not json"
    assert second[2]["role"] == "user"
    assert "not JSON" in second[2]["content"]


# ---- validation failure ---------------------------------------------------


async def test_replays_assistant_turn_on_validation_failure() -> None:
    def _reject_odd(parsed: _Schema) -> None:
        if parsed.value % 2 == 1:
            msg = f"value {parsed.value} is odd"
            raise ValueError(msg)

    chat = _StubChat([_ok(3, content='{"value": 3}'), _ok(4, content='{"value": 4}')])
    messages: list[Any] = [{"role": "user", "content": "hi"}]
    result = await _invoke(chat, messages, validate=_reject_odd)

    assert result.value == 4
    second = chat.invocations[1]
    assert isinstance(second[1], AIMessage)
    assert second[1].content == '{"value": 3}'
    assert "value 3 is odd" in second[2]["content"]


# ---- transport failure ----------------------------------------------------


async def test_retries_on_transport_failure_without_appending_assistant_turn() -> None:
    """Reproduction of the prod failure: OpenAI SDK raised TypeError for `choices: null`.

    On a transport-level failure there is no assistant turn to replay, so the helper must retry with the existing conversation unchanged. Otherwise the second attempt would carry phantom assistant content and confuse the model.
    """
    chat = _StubChat(
        [
            TypeError("'NoneType' object is not iterable"),
            _ok(1),
        ]
    )
    messages: list[Any] = [{"role": "user", "content": "hi"}]
    result = await _invoke(chat, messages)

    assert result.value == 1
    assert len(chat.invocations) == 2
    # Both invocations see the same single user message — no phantom assistant turn appended after the failed call.
    assert chat.invocations[0] == [{"role": "user", "content": "hi"}]
    assert chat.invocations[1] == [{"role": "user", "content": "hi"}]


async def test_exhausts_retries_and_raises_with_transport_error() -> None:
    chat = _StubChat(
        [
            TypeError("'NoneType' object is not iterable"),
            TypeError("'NoneType' object is not iterable"),
        ]
    )
    with pytest.raises(StructuredRetryError) as exc_info:
        await _invoke(chat, [{"role": "user", "content": "hi"}], max_retries=1)

    assert exc_info.value.attempts == 2
    assert "TypeError" in exc_info.value.last_error


def test_dated_system_prompt_prepends_today_and_keeps_base() -> None:
    from datetime import UTC, datetime

    base = "You are a research analyst."
    result = dated_system_prompt(base)

    assert result.endswith(base)
    # The current year anchors the model to the present (the bug was models
    # assuming their training-cutoff year).
    assert str(datetime.now(UTC).year) in result
    assert "as of 2023" in result  # the explicit anti-pattern callout
