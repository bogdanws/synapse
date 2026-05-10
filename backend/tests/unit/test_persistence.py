"""Unit tests for the pure-mapping helpers in `app.services.persistence`.

Real DB roundtrips are integration territory and are exercised in `tests/integration/test_orm.py`. These tests cover the format contract that lives outside the database — what the JSONB blob and `Source` rows actually look like.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.research import (
    Contradiction,
    ReportSection,
    ScribeReport,
    Source,
)
from app.services.persistence import _report_body_jsonb, _to_source_orm


def _source(short_id: str = "s1") -> Source:
    return Source(
        id=short_id,
        url="https://example.com/x",  # type: ignore[arg-type]
        title=f"Source {short_id}",
        author="A. Author",
        published_at=datetime(2024, 1, 1, tzinfo=UTC),
        credibility=0.7,
        relevance=0.8,
        snippet="snippet",
    )


def test_to_source_orm_copies_fields_and_sets_short_id() -> None:
    job_id = uuid4()
    src = _source("s7")
    row = _to_source_orm(job_id, src)
    assert row.job_id == job_id
    assert row.short_id == "s7"
    assert row.url == "https://example.com/x"
    assert row.title == "Source s7"
    assert row.author == "A. Author"
    assert row.snippet == "snippet"
    assert row.credibility == pytest.approx(0.7)
    assert row.relevance == pytest.approx(0.8)
    # Source content is intentionally not persisted yet (see module docstring).
    assert row.content is None


def test_report_body_jsonb_is_round_trippable_json() -> None:
    job_id = uuid4()
    report_id = uuid4()
    report = ScribeReport(
        id=report_id,
        job_id=job_id,
        topic="Quantum",
        title="T",
        summary_md="s",
        sections=[
            ReportSection(
                id="sec1",
                heading="H",
                body_md='<span data-claim="sec1.c1">x[^s1]</span>',
            )
        ],
        sources=[_source("s1")],
        contradictions=[Contradiction(description="d", source_ids=["s1"])],
        follow_ups=["What about Y?"],
        generated_at=datetime.now(UTC),
        model="m",
    )
    blob = _report_body_jsonb(report)

    # The hot fields kept as columns are intentionally absent from the JSONB
    # blob; everything else is preserved exactly so a future evolution of the
    # report shape doesn't require a migration.
    assert "title" not in blob
    assert "summary_md" not in blob
    assert "model" not in blob
    assert "generated_at" not in blob
    assert blob["topic"] == "Quantum"
    assert blob["id"] == str(report_id)
    assert isinstance(blob["sections"], list)
    assert blob["sections"][0]["id"] == "sec1"
    assert isinstance(blob["sources"], list)
    assert blob["sources"][0]["id"] == "s1"
    assert blob["contradictions"][0]["description"] == "d"
    assert blob["follow_ups"] == ["What about Y?"]
