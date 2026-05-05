"""Scout - research agent.

Decomposes a user topic into sub-questions, searches multiple sources,
and evaluates relevance & credibility.
"""

from __future__ import annotations

from app.models.research import SourceData


class ScoutAgent:
    """Stub. Implementation lands in a later sprint."""

    def __init__(self, model: str) -> None:
        # TODO: build LLM client from `model` (OpenRouter id), wire Exa client
        # and scraping tools.
        self.model = model

    async def decompose(self, topic: str) -> list[str]:
        """Break a topic into sub-questions."""
        raise NotImplementedError

    async def search(self, query: str) -> list[SourceData]:
        """Run a query against external sources."""
        raise NotImplementedError

    async def evaluate(self, sources: list[SourceData]) -> list[SourceData]:
        """Score relevance for each source."""
        raise NotImplementedError

    async def score_source(self, source: SourceData) -> float:
        """Return credibility score in [0, 1]."""
        raise NotImplementedError

    async def deduplicate(self, sources: list[SourceData]) -> list[SourceData]:
        """Remove near-duplicates by URL / content fingerprint."""
        raise NotImplementedError
