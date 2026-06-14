"""Unit tests for the domain-credibility heuristic and the blend rule."""

from __future__ import annotations

import pytest

from app.services.credibility import (
    _NO_SIGNAL_CREDIBILITY,
    _PRIOR_WEIGHT,
    combine_credibility,
    domain_prior,
)


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


def test_unknown_host_has_no_prior() -> None:
    # `.com` carries no TLD prior, so an unfamiliar commercial host yields no signal.
    assert domain_prior("https://unknown-blog.example/post") is None
    assert domain_prior("https://anthropic.com/news") is None
    assert domain_prior("https://platform.claude.com/docs") is None


def test_subdomains_inherit_host_prior() -> None:
    # Verifies the suffix match: deeply nested subdomains still resolve.
    assert domain_prior("https://blog.research.nature.com/article") == 0.95


def test_empty_or_malformed_url_has_no_prior() -> None:
    assert domain_prior("") is None
    assert domain_prior("not-a-url") is None


def test_combine_unknown_host_defers_to_llm() -> None:
    # The previous default-prior product capped unknown hosts; now a strong LLM rating carries through.
    assert combine_credibility(None, 0.8) == pytest.approx(0.8)


def test_combine_known_host_blends_toward_prior() -> None:
    blended = combine_credibility(0.95, 0.5)
    assert blended == pytest.approx(_PRIOR_WEIGHT * 0.95 + (1 - _PRIOR_WEIGHT) * 0.5)
    # A curated prior stays dominant: the blend sits closer to the prior than to the rating.
    assert abs(blended - 0.95) < abs(blended - 0.5)


def test_combine_missing_llm_rating_uses_prior_alone() -> None:
    assert combine_credibility(0.92, None) == pytest.approx(0.92)


def test_combine_no_signal_at_all_is_neutral() -> None:
    assert combine_credibility(None, None) == pytest.approx(_NO_SIGNAL_CREDIBILITY)
