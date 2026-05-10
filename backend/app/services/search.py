"""Async Exa search client with trafilatura fallback.

Wraps Exa's REST API directly via httpx instead of the bundled `exa-py` so:

1. The whole call path is async — no `asyncio.to_thread` around a sync SDK.
2. Tests can mock at the httpx layer with `respx`, matching the project's
   chosen testing pattern.

When Exa returns a result without text content, we try `trafilatura` on the URL as a fallback. If that also fails, the source is kept with whatever snippet/title Exa supplied so the user can still cite it manually; downstream scoring may down-rank it via the LLM.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
import structlog
import trafilatura
from pydantic import BaseModel, Field

from app.config import get_settings

_log = structlog.get_logger(__name__)

EXA_BASE_URL = "https://api.exa.ai"
_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_DEFAULT_NUM_RESULTS = 5
# Exa returns up to 10k chars by default; the snippet we keep is much smaller. Capping the stored body keeps DB rows compact and avoids re-tokenising massive pages downstream.
_CONTENT_MAX_CHARS = 8000
_SNIPPET_MAX_CHARS = 600


class ExaResult(BaseModel):
    """Subset of Exa's `/search` result we use. Extras are ignored."""

    url: str
    title: str = ""
    author: str | None = None
    published_date: str | None = Field(default=None, alias="publishedDate")
    text: str | None = None

    @property
    def parsed_published_at(self) -> datetime | None:
        if not self.published_date:
            return None
        # Exa uses ISO-8601 with Z; fromisoformat accepts the +HH:MM form on 3.11+ but not Z without normalisation.
        normalised = self.published_date.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalised)
        except ValueError:
            return None


class ExaSearchClient:
    """Thin async wrapper over Exa's `/search` endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else get_settings().exa_api_key
        # Caller-owned client takes precedence so tests can share a respx-mocked transport across calls.
        self._http: httpx.AsyncClient = http_client or httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def search(
        self, query: str, *, num_results: int = _DEFAULT_NUM_RESULTS
    ) -> list[ExaResult]:
        """Run a single search; returns up to `num_results` parsed results.

        Raises `httpx.HTTPStatusError` on non-2xx responses and `httpx.RequestError` on network failures.
        Callers that want per-query soft-failure semantics (e.g. `run_scout`) should catch these and continue with the remaining sub-questions.
        """
        body: dict[str, Any] = {
            "query": query,
            "type": "auto",
            "numResults": num_results,
            "contents": {"text": {"maxCharacters": _CONTENT_MAX_CHARS}},
        }
        headers = {"x-api-key": self._api_key, "Content-Type": "application/json"}
        response = await self._http.post(f"{EXA_BASE_URL}/search", json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", [])
        return [ExaResult.model_validate(item) for item in raw_results]


async def fetch_article_text(url: str, *, timeout: float = 15.0) -> str | None:
    """Fetch and extract the main article text for a URL using trafilatura.

    Returns `None` if the page can't be downloaded or trafilatura can't recover prose. Runs the synchronous trafilatura calls in a worker thread because both `fetch_url` and `extract` block on network and parsing respectively.
    """
    try:
        downloaded = await asyncio.wait_for(
            asyncio.to_thread(trafilatura.fetch_url, url),
            timeout=timeout,
        )
    except (TimeoutError, OSError) as exc:
        _log.warning("trafilatura_fetch_failed", url=url, error=str(exc))
        return None
    if not downloaded:
        return None
    text = await asyncio.to_thread(
        trafilatura.extract,
        downloaded,
        include_comments=False,
        include_tables=False,
    )
    if not text:
        return None
    return text[:_CONTENT_MAX_CHARS]


def derive_snippet(text: str | None, fallback: str = "") -> str:
    """Pick a short excerpt suitable for the `Source.snippet` field."""
    if not text:
        return fallback[:_SNIPPET_MAX_CHARS]
    cleaned = " ".join(text.split())
    return cleaned[:_SNIPPET_MAX_CHARS]
