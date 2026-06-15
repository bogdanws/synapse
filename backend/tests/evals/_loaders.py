"""Typed loaders for eval fixture JSON files.

Each loader reads a file from `data/`, validates its contents through the
production Pydantic models, and returns typed dataclasses. Fixture errors
surface at collection time (loaders are called at module level for
`pytest.mark.parametrize`) rather than mid-test, which is the intended
fail-fast behaviour.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.research import (
    Contradiction,
    ReportSection,
    ScribeReport,
    Source,
)
from app.services.validation import validate_scribe_report

_DATA_DIR = Path(__file__).parent / "data"


# ---- Scout ------------------------------------------------------------------


@dataclass
class ScoutTopic:
    id: str
    topic: str


def load_scout_topics() -> list[ScoutTopic]:
    raw_list: list[dict[str, Any]] = json.loads((_DATA_DIR / "scout_topics.json").read_text())
    return [ScoutTopic(id=item["id"], topic=item["topic"]) for item in raw_list]


# ---- Scribe -----------------------------------------------------------------


@dataclass
class ScribeCase:
    id: str
    topic: str
    sub_questions: list[str]
    sources: list[Source]


def load_scribe_cases() -> list[ScribeCase]:
    raw_list: list[dict[str, Any]] = json.loads((_DATA_DIR / "scribe_cases.json").read_text())
    return [
        ScribeCase(
            id=item["id"],
            topic=item["topic"],
            sub_questions=list(item["sub_questions"]),
            sources=[Source.model_validate(s) for s in item["sources"]],
        )
        for item in raw_list
    ]


# ---- Critic -----------------------------------------------------------------


@dataclass
class CriticCase:
    id: str
    topic: str
    report: ScribeReport
    labels: dict[str, str]  # claim_id -> "supported" | "false"


def load_critic_cases() -> list[CriticCase]:
    raw_list: list[dict[str, Any]] = json.loads((_DATA_DIR / "critic_cases.json").read_text())
    cases: list[CriticCase] = []
    for raw in raw_list:
        sources = [Source.model_validate(s) for s in raw["sources"]]
        sections = [
            ReportSection(
                id=s["id"],
                heading=s["heading"],
                body_md=s["body_md"],
            )
            for s in raw["sections"]
        ]
        contradictions = [Contradiction.model_validate(c) for c in raw.get("contradictions", [])]
        report = ScribeReport(
            id=uuid4(),
            job_id=uuid4(),
            topic=raw["topic"],
            title=raw["title"],
            summary_md=raw["summary_md"],
            sections=sections,
            sources=sources,
            contradictions=contradictions,
            follow_ups=list(raw.get("follow_ups", [])),
            generated_at=datetime.now(UTC),
            model="fixture",
        )
        # Fail at collection time if the fixture violates the production contract.
        validate_scribe_report(report)
        cases.append(
            CriticCase(
                id=raw["id"],
                topic=raw["topic"],
                report=report,
                labels={str(k): str(v) for k, v in raw["labels"].items()},
            )
        )
    return cases
