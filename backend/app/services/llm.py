"""LangChain ChatOpenAI factory pre-configured for OpenRouter.

OpenRouter is OpenAI-API-compatible, so we point `langchain-openai`'s `ChatOpenAI` at its base URL and pass the OpenRouter key. The model id is supplied per-request (the user picks a different model per agent), so this module only manages the transport layer.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import get_settings

# OpenRouter's stable v1 endpoint. Hard-coded rather than read from env because every reachable OpenRouter deployment shares this prefix and pinning it here keeps tests' respx mounts simple.
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def build_chat_model(model: str, *, temperature: float = 0.0) -> ChatOpenAI:
    """Construct a `ChatOpenAI` bound to OpenRouter for the given model id.

    `temperature=0` is the default because every agent in this pipeline expects deterministic, structured output; callers can override per call (e.g. the Scribe summary section may benefit from a small amount of randomness later).
    """
    settings = get_settings()
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,  # type: ignore[arg-type]
        base_url=OPENROUTER_BASE_URL,
        temperature=temperature,
    )


def dated_system_prompt(prompt: str) -> str:
    """Prepend today's date to a static agent system prompt.

    Models anchor on their training cutoff and read relative time expressions —
    "current", "latest", "now", "recent" — as of that cutoff. Concretely, Scout
    was decomposing "the current Prime Minister of Romania" into "...as of
    October 2023". Stating today's date re-anchors the model to the present.

    Computed per call, not at import: the worker process is long-lived (days), so
    an import-time timestamp would silently go stale. UTC keeps it deterministic
    across deployments and matches the rest of the pipeline's timestamps.
    """
    today = datetime.now(UTC).strftime("%A, %d %B %Y")
    preamble = (
        f"Today's date is {today} (UTC). Treat this as the present: interpret "
        '"current", "latest", "now", and "recent" relative to today, not to your '
        "training cutoff, and never silently narrow a question to an earlier year "
        '(e.g. do not rewrite "current" as "as of 2023").'
    )
    return f"{preamble}\n\n{prompt}"


class StructuredRetryError(RuntimeError):
    """All structured-output retries failed.

    Wraps the final attempt's error string so callers can re-raise as a domain-specific exception with their own message format. We surface a typed error rather than a bare `RuntimeError` so handlers can distinguish "model output kept failing" from genuine programmer bugs.

    The wrapped error covers three failure modes the helper retries through: invalid JSON / wrong schema (parser failure), validator-raised exceptions (semantic failure), and exceptions during the LLM invocation itself (transport / upstream-malformed-response failure, e.g. OpenRouter returning `choices: null` and the OpenAI SDK choking on it).
    """

    def __init__(self, attempts: int, last_error: str) -> None:
        super().__init__(
            f"structured output retries exhausted after {attempts} attempts: {last_error}"
        )
        self.attempts = attempts
        self.last_error = last_error


async def invoke_structured_with_retry[T: BaseModel](
    chat: Runnable[Any, dict[str, Any]],
    messages: list[Any],
    *,
    validate: Callable[[T], None],
    retry_feedback: Callable[[str], str],
    max_retries: int,
    log_event: str,
    log: Any,
) -> T:
    """Run a structured-output LLM call with conversation-aware retries across three failure modes.

    `chat` must already have `with_structured_output(..., include_raw=True)` applied so each invocation returns `{"raw": AIMessage, "parsed": T | None, "parsing_error": ...}`. Without `include_raw=True`, JSON-parse failures bubble up as exceptions and we never see a chance to retry.

    Failure modes handled:

    1. **Upstream/transport failure** — `chat.ainvoke` itself raises (e.g. provider returned `choices: null` and the OpenAI SDK choked, network blip, 5xx). Retried with the existing conversation unchanged because there is no assistant turn to append.
    2. **Schema/parse failure** — the response was received but couldn't be coerced into the target schema (`parsed is None`). The model's exact bytes are appended as an assistant turn and a corrective user turn follows so the model can see what it sent.
    3. **Validator failure** — the response parsed but the caller's `validate` raised. Same replay-and-correct treatment as the parse failure case.

    Mutation note: `messages` is appended to *in place* on every retry. Callers should treat the list as owned by this function for the duration of the call.

    `validate` is called with the parsed schema; raise *any* exception from it to trigger a retry (the exception's `str()` becomes the feedback shown to the model). `retry_feedback` formats that feedback into the user turn — agents customise this so they can re-state the schema if useful.

    Raises `StructuredRetryError` after `max_retries + 1` total attempts. Callers typically catch this and re-raise as a domain-specific exception (e.g. `ScribeValidationError`).
    """
    last_error: str | None = None
    attempts = max_retries + 1
    for attempt in range(attempts):
        try:
            result = await chat.ainvoke(messages)
        except Exception as exc:  # noqa: BLE001
            # Upstream/transport failure: the request never produced a parseable response (e.g. OpenRouter returned a 200 with `choices: null` and the OpenAI SDK raised TypeError trying to iterate; transient network blip; provider 5xx). Treated as retryable because these are usually transient. We do not append an assistant turn — there is none — so the next attempt re-uses the existing conversation unchanged.
            last_error = f"call to model failed: {type(exc).__name__}: {exc}"
            log.warning(log_event, attempt=attempt + 1, error=last_error, exc_info=True)
            continue

        raw_message = result["raw"]
        parsed = result["parsed"]
        parsing_error = result.get("parsing_error")

        if parsed is None:
            last_error = f"output was not valid JSON for the required schema: {parsing_error}"
        else:
            try:
                # The validator's contract is "raise to indicate retry". Any exception type is fair game — the helper has no way to know the caller's domain exception hierarchy, and constraining it would force every caller to translate. BLE001 is silenced for that reason.
                validate(cast("T", parsed))
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            else:
                return cast("T", parsed)

        log.warning(log_event, attempt=attempt + 1, error=last_error)
        messages.append(raw_message)
        messages.append({"role": "user", "content": retry_feedback(last_error)})

    # `last_error` is always set by the time we reach here: the loop runs at
    # least once and any path through the body assigns to it before reaching
    # the trailing append.
    assert last_error is not None
    raise StructuredRetryError(attempts, last_error)
