"""Pipeline orchestrator: coordinates Scout -> Scribe -> Critic.

Will eventually emit progress events over WebSocket and persist artifacts
to PostgreSQL / Redis.
"""

from __future__ import annotations

from app.agents.critic import CriticAgent
from app.agents.scout import ScoutAgent
from app.agents.scribe import ScribeAgent
from app.models.research import VerifiedReport


class Orchestrator:
    """Stub. Implementation lands in a later sprint.

    Each agent gets its own model, chosen by the user per request.
    """

    def __init__(
        self,
        scout: ScoutAgent,
        scribe: ScribeAgent,
        critic: CriticAgent,
    ) -> None:
        self.scout = scout
        self.scribe = scribe
        self.critic = critic

    async def run(self, topic: str) -> VerifiedReport:
        """Execute the full Scout -> Scribe -> Critic pipeline."""
        raise NotImplementedError
