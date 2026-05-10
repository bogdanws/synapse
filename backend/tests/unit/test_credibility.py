"""Unit tests for the domain-credibility heuristic."""

from __future__ import annotations

import pytest

from app.services.credibility import DEFAULT_PRIOR, domain_prior


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.nature.com/articles/d41586-024-00001-2", 0.95),
        ("https://nih.gov/health", 0.95),
        ("https://www.bbc.co.uk/news/world-1", 0.80),
        ("https://en.wikipedia.org/wiki/Topic", 0.65),
        ("https://www.reddit.com/r/topic/comments/x", 0.30),
        ("https://twitter.com/user/status/1", 0.30),
    ],
)
def test_known_hosts_use_explicit_prior(url: str, expected: float) -> None:
    assert domain_prior(url) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://nasa.gov/missions", 0.95),
        ("https://example.edu/dept", 0.90),
        ("https://example.mil/div", 0.90),
        ("https://example.int/area", 0.85),
    ],
)
def test_tld_priors_apply_when_host_unknown(url: str, expected: float) -> None:
    assert domain_prior(url) == expected


def test_unknown_host_falls_back_to_default() -> None:
    assert domain_prior("https://unknown-blog.example/post") == DEFAULT_PRIOR


def test_subdomains_inherit_host_prior() -> None:
    # Verifies the suffix match: deeply nested subdomains still resolve.
    assert domain_prior("https://blog.research.nature.com/article") == 0.95


def test_empty_or_malformed_url_returns_default() -> None:
    assert domain_prior("") == DEFAULT_PRIOR
    assert domain_prior("not-a-url") == DEFAULT_PRIOR
