"""Domain-based credibility prior for sources, and the rule that blends it with the LLM rating.

`domain_prior` maps the registrable host of a URL to a curated prior in [0, 1], or `None` when the host is unknown. `combine_credibility` then folds that prior together with Scout's per-source LLM rating to produce the final `Source.credibility`.

The key design choice: an unknown host carries *no* credibility signal, so we defer entirely to the LLM rather than anchoring on a made-up default. A multiplicative default-prior model (the previous approach) capped legitimate-but-unfamiliar outlets — e.g. an official vendor or documentation site — at the default, which the LLM could only ever drag lower. Deferring fixes that floor without hardcoding more hosts.
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

# Weight on the curated domain prior when blending with the LLM rating for a *known* host. The LLM is explicitly told not to judge domain reputation, so it should only lightly nudge a curated prior, not override it. Must stay in [0, 1].
_PRIOR_WEIGHT = 0.7

# Credibility used only when we have no signal at all: unknown host *and* no LLM rating (e.g. the rating call failed). Deliberately neutral.
_NO_SIGNAL_CREDIBILITY = 0.5


def domain_prior(url: str) -> float | None:
    """Return the credibility prior in [0, 1] for the given URL's host, or `None` if unknown.

    Resolution order (first match wins): explicit host in `_HOST_PRIORS` → TLD in `_TLD_PRIORS` → `None`. `None` means "no domain-level signal"; callers should defer to other evidence rather than substituting a default.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().lstrip(".")
    if not host:
        return None

    for known, score in _HOST_PRIORS.items():
        if host == known or host.endswith("." + known):
            return score

    tld = host.rsplit(".", 1)[-1]
    if tld in _TLD_PRIORS:
        return _TLD_PRIORS[tld]

    return None


def combine_credibility(prior: float | None, llm_cred: float | None) -> float:
    """Fold a domain prior and an LLM rating into a final credibility in [0, 1].

    - Both present: weighted arithmetic mean, anchored on the curated prior (`_PRIOR_WEIGHT`). The mean can lift or lower the prior, unlike the old product which could only shrink it, but the weight keeps a curated prior dominant.
    - Unknown host (`prior is None`): defer to the LLM rating; the domain tells us nothing.
    - LLM rating missing (`llm_cred is None`): anchor on the prior alone.
    - Neither signal: fall back to a neutral constant.
    """
    if prior is None:
        return _NO_SIGNAL_CREDIBILITY if llm_cred is None else llm_cred
    if llm_cred is None:
        return prior
    return _PRIOR_WEIGHT * prior + (1.0 - _PRIOR_WEIGHT) * llm_cred
