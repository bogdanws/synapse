"""Scribe - synthesis agent.

Turns Scout's raw sources into a structured, cited report.
"""

from __future__ import annotations

from app.models.research import Report, SourceData


class ScribeAgent:
    """Stub. Implementation lands in a later sprint."""

    def __init__(self, model: str) -> None:
        # TODO: build LLM client from `model` (OpenRouter id) and prompt template.
        self.model = model

    async def synthesize(self, topic: str, sources: list[SourceData]) -> Report:
        """Synthesise a structured report with citations & summary."""
        raise NotImplementedError

    async def contradictions(self, sources: list[SourceData]) -> list[str]:
        """Identify contradictions between sources."""
        raise NotImplementedError
