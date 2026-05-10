"""Tests for the async Exa search client.

We mock the Exa REST endpoint with respx so the tests stay deterministic and offline. trafilatura's fetch path runs against a tiny in-process httpx mock too.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.search import (
    EXA_BASE_URL,
    ExaResult,
    ExaSearchClient,
    derive_snippet,
)


def test_exa_result_parses_published_date() -> None:
    r = ExaResult.model_validate(
        {
            "url": "https://example.com/x",
            "title": "T",
            "publishedDate": "2024-05-01T12:00:00Z",
            "text": "body",
        }
    )
    parsed = r.parsed_published_at
    assert parsed is not None
    assert parsed.year == 2024


def test_exa_result_handles_missing_published_date() -> None:
    r = ExaResult.model_validate({"url": "https://example.com/x"})
    assert r.parsed_published_at is None


def test_exa_result_ignores_unparseable_date() -> None:
    r = ExaResult.model_validate({"url": "https://example.com/x", "publishedDate": "not-a-date"})
    assert r.parsed_published_at is None


@pytest.mark.respx(base_url=EXA_BASE_URL)
async def test_search_posts_to_exa_and_parses_results(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com/a",
                        "title": "Alpha",
                        "author": "Ada",
                        "publishedDate": "2024-01-01T00:00:00Z",
                        "text": "Alpha body text.",
                    },
                    {
                        "url": "https://example.com/b",
                        "title": "Beta",
                    },
                ]
            },
        )
    )

    async with httpx.AsyncClient() as http:
        client = ExaSearchClient(api_key="k", http_client=http)
        results = await client.search("quantum")

    assert len(results) == 2
    assert results[0].url == "https://example.com/a"
    assert results[0].text == "Alpha body text."
    assert results[1].text is None


@pytest.mark.respx(base_url=EXA_BASE_URL)
async def test_search_raises_on_http_error(respx_mock: respx.MockRouter) -> None:
    respx_mock.post("/search").mock(return_value=httpx.Response(500, json={"error": "boom"}))
    async with httpx.AsyncClient() as http:
        client = ExaSearchClient(api_key="k", http_client=http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.search("quantum")


def test_derive_snippet_collapses_whitespace_and_truncates() -> None:
    text = "  hello\n   world\t" + ("x" * 1000)
    snippet = derive_snippet(text)
    assert snippet.startswith("hello world ")
    assert len(snippet) <= 600


def test_derive_snippet_uses_fallback_when_text_empty() -> None:
    assert derive_snippet(None, fallback="t") == "t"
    assert derive_snippet("", fallback="t") == "t"
