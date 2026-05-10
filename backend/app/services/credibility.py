"""Domain-based credibility prior for sources.

Pure heuristic: maps the registrable host of a URL to a prior in [0, 1]. Scout multiplies this with an LLM rating to produce the final `Source.credibility`, so unfamiliar but legitimate outlets aren't punished here — the LLM pass adjusts those.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Explicit per-host priors, matched as suffixes so subdomains inherit. High scores for peer-reviewed publishers and major news organisations; low scores for hosts dominated by user-generated content. Ordered alphabetically; add a regression test in `tests/unit/test_credibility.py` for any new entry.
_HOST_PRIORS: dict[str, float] = {
    "arxiv.org": 0.85,
    "bbc.co.uk": 0.80,
    "bbc.com": 0.80,
    "medium.com": 0.40,
    "nature.com": 0.95,
    "nejm.org": 0.95,
    "nih.gov": 0.95,
    "npr.org": 0.80,
    "nytimes.com": 0.78,
    "pnas.org": 0.92,
    "quora.com": 0.30,
    "reddit.com": 0.30,
    "reuters.com": 0.85,
    "science.org": 0.92,
    "sciencedirect.com": 0.85,
    "scientificamerican.com": 0.80,
    "springer.com": 0.85,
    "substack.com": 0.45,
    "theguardian.com": 0.78,
    "tumblr.com": 0.25,
    "twitter.com": 0.30,
    "washingtonpost.com": 0.78,
    "who.int": 0.92,
    "wikipedia.org": 0.65,
    "wordpress.com": 0.40,
    "x.com": 0.30,
}

# Coarse fallback by top-level domain when the host isn't in `_HOST_PRIORS`.
_TLD_PRIORS: dict[str, float] = {
    "gov": 0.95,
    "edu": 0.90,
    "mil": 0.90,
    "int": 0.85,
}

DEFAULT_PRIOR = 0.55


def domain_prior(url: str) -> float:
    """Return the credibility prior in [0, 1] for the given URL's host.

    Resolution order (first match wins): explicit host in `_HOST_PRIORS` → TLD in `_TLD_PRIORS` → `DEFAULT_PRIOR`.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().lstrip(".")
    if not host:
        return DEFAULT_PRIOR

    for known, score in _HOST_PRIORS.items():
        if host == known or host.endswith("." + known):
            return score

    tld = host.rsplit(".", 1)[-1]
    if tld in _TLD_PRIORS:
        return _TLD_PRIORS[tld]

    return DEFAULT_PRIOR
