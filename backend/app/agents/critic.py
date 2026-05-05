"""Critic - fact-checking agent.

Verifies the Scribe report against the original sources, scores confidence
per section, flags unsupported claims (hallucinations).
"""

from __future__ import annotations

from app.models.research import Report, SourceData, VerifiedReport


class CriticAgent:
    """Stub. Implementation lands in a later sprint."""

    def __init__(self, model: str) -> None:
        # TODO: build LLM client from `model` (OpenRouter id) and retrieval over sources.
        self.model = model

    async def verify(self, report: Report, sources: list[SourceData]) -> VerifiedReport:
        """Verify each claim in the report against sources."""
        raise NotImplementedError

    async def score_section(self, section_text: str, sources: list[SourceData]) -> float:
        """Compute confidence score in [0, 1] for one section."""
        raise NotImplementedError

    async def flag_hallucinations(self, report: Report, sources: list[SourceData]) -> list[str]:
        """Return a list of flagged unsupported claims."""
        raise NotImplementedError
