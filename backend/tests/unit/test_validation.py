"""Tests for the Scribe / Critic structural validators."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.research import (
    ClaimFlag,
    Contradiction,
    ContradictionPosition,
    CriticAnnotations,
    ReportSection,
    ScribeReport,
    SectionConfidence,
    Source,
    Verdict,
)
from app.services.validation import (
    CriticValidationError,
    ScribeValidationError,
    validate_critic_annotations,
    validate_scribe_report,
)

# ---- factories -------------------------------------------------------------


def _source(short_id: str, url: str = "https://example.com/x") -> Source:
    return Source(
        id=short_id,
        url=url,  # type: ignore[arg-type]
        title="t",
        credibility=0.5,
        relevance=0.5,
        snippet="s",
    )


def _section(
    section_id: str,
    *,
    body_md: str,
    heading: str = "h",
) -> ReportSection:
    # `cited_source_ids` is derived from `body_md` by the model itself; tests that need to assert on the derived list do so via the constructed instance rather than by passing it in.
    return ReportSection(id=section_id, heading=heading, body_md=body_md)


def _report(sections: list[ReportSection], sources: list[Source] | None = None) -> ScribeReport:
    return ScribeReport(
        id=uuid4(),
        job_id=uuid4(),
        topic="t",
        title="T",
        summary_md="s",
        sections=sections,
        sources=sources or [_source("s1"), _source("s2")],
        contradictions=[],
        follow_ups=[],
        generated_at=datetime.now(UTC),
        model="test/model",
    )


def _annotations(
    report: ScribeReport,
    *,
    claim_flags: list[ClaimFlag] | None = None,
    section_confidence: list[SectionConfidence] | None = None,
) -> CriticAnnotations:
    return CriticAnnotations(
        id=uuid4(),
        report_id=report.id,
        section_confidence=section_confidence or [],
        claim_flags=claim_flags or [],
        overall_confidence=0.7,
        model="test/model",
        generated_at=datetime.now(UTC),
    )


# ---- happy path ------------------------------------------------------------


def test_valid_report_passes() -> None:
    section = _section(
        "sec1",
        body_md=(
            'Intro <span data-claim="sec1.c1">first claim[^s1]</span>.\n\n'
            'More text <span data-claim="sec1.c2">second claim[^s2]</span>.\n'
        ),
    )
    validate_scribe_report(_report([section]))


def test_cited_source_ids_are_derived_from_body_md() -> None:
    """The field is server-derived; whatever is passed in is overwritten.

    We only assert on first-occurrence ordering here. Footnote-vs-source consistency is the validator's job and is covered separately below.
    """
    section = ReportSection(
        id="sec1",
        heading="h",
        body_md=(
            '<span data-claim="sec1.c1">a[^s2][^s1]</span> '
            '<span data-claim="sec1.c2">b[^s2][^s3]</span>'
        ),
        cited_source_ids=["s99"],  # ignored — derivation overwrites
    )
    assert section.cited_source_ids == ["s2", "s1", "s3"]


def test_cited_source_ids_accept_refs_without_caret() -> None:
    section = ReportSection(
        id="sec1",
        heading="h",
        body_md='<span data-claim="sec1.c1">a[s2][^s1]</span>',
    )
    assert section.cited_source_ids == ["s2", "s1"]


# ---- section ids -----------------------------------------------------------


def test_rejects_empty_sections() -> None:
    with pytest.raises(ScribeValidationError, match="no sections"):
        validate_scribe_report(_report([]))


def test_rejects_non_sequential_section_ids() -> None:
    sections = [
        _section("sec1", body_md=""),
        _section("sec3", body_md=""),  # gap
    ]
    with pytest.raises(ScribeValidationError, match="expected 'sec2'"):
        validate_scribe_report(_report(sections))


def test_rejects_malformed_section_id() -> None:
    sections = [_section("section-1", body_md="")]
    with pytest.raises(ScribeValidationError, match="expected 'sec1'"):
        validate_scribe_report(_report(sections))


# ---- claim spans -----------------------------------------------------------


def test_rejects_claim_with_wrong_section_prefix() -> None:
    section = _section(
        "sec1",
        body_md='<span data-claim="sec2.c1">x[^s1]</span>',
    )
    with pytest.raises(ScribeValidationError, match="expected 'sec1'"):
        validate_scribe_report(_report([section]))


def test_rejects_non_sequential_claim_ids() -> None:
    section = _section(
        "sec1",
        body_md=(
            '<span data-claim="sec1.c1">a[^s1]</span> <span data-claim="sec1.c3">b[^s1]</span>'
        ),
    )
    with pytest.raises(ScribeValidationError, match="expected next claim 'c2'"):
        validate_scribe_report(_report([section]))


def test_rejects_duplicate_claim_id_in_section() -> None:
    section = _section(
        "sec1",
        body_md=(
            '<span data-claim="sec1.c1">a[^s1]</span> <span data-claim="sec1.c1">b[^s1]</span>'
        ),
    )
    with pytest.raises(ScribeValidationError, match="more than once"):
        validate_scribe_report(_report([section]))


def test_rejects_claim_id_without_section_prefix() -> None:
    section = _section(
        "sec1",
        body_md='<span data-claim="c1">orphan[^s1]</span>',
    )
    with pytest.raises(ScribeValidationError, match="missing the section prefix"):
        validate_scribe_report(_report([section]))


# ---- footnote refs ---------------------------------------------------------


def test_rejects_footnote_ref_to_unknown_source() -> None:
    section = _section(
        "sec1",
        body_md='<span data-claim="sec1.c1">a[^s99]</span>',
    )
    with pytest.raises(ScribeValidationError, match="\\['s99'\\]"):
        validate_scribe_report(_report([section]))


def test_rejects_ref_without_caret_to_unknown_source() -> None:
    section = _section(
        "sec1",
        body_md='<span data-claim="sec1.c1">a[s99]</span>',
    )
    with pytest.raises(ScribeValidationError, match="\\['s99'\\]"):
        validate_scribe_report(_report([section]))


def test_rejects_citation_outside_claim_span() -> None:
    """A `[^sX]` that is not wrapped in a claim span is unverifiable by the Critic.

    Regression for a report whose Scribe model emitted bare footnotes for every
    sentence and wrapped none of them, yielding a report with zero claims.
    """
    section = _section(
        "sec1",
        body_md=(
            'Wrapped <span data-claim="sec1.c1">claim[^s1]</span>. '
            "But this fact is cited outside any span[^s2]."
        ),
    )
    with pytest.raises(ScribeValidationError, match="outside a <span data-claim> span"):
        validate_scribe_report(_report([section]))


def test_rejects_section_with_only_orphan_citations() -> None:
    """The exact failure mode seen in production: prose with citations, no spans."""
    section = _section(
        "sec1",
        body_md="DeepSeek V4 Pro was released under an MIT license[^s1][^s2].",
    )
    with pytest.raises(ScribeValidationError, match="outside a <span data-claim> span"):
        validate_scribe_report(_report([section]))


def test_accepts_footnote_definition_outside_span() -> None:
    """A definition line (`[^sX]: …`) is bibliography-like, not an in-prose claim."""
    section = _section(
        "sec1",
        body_md=('<span data-claim="sec1.c1">claim[^s1]</span>\n\n[^s1]: Source one.\n'),
    )
    validate_scribe_report(_report([section]))


# ---- contradictions --------------------------------------------------------


def _report_with_contradictions(
    contradictions: list[Contradiction], sources: list[Source]
) -> ScribeReport:
    section = _section("sec1", body_md='<span data-claim="sec1.c1">a[^s1]</span>')
    base = _report([section], sources=sources)
    return ScribeReport(**{**base.model_dump(), "contradictions": contradictions})


def test_contradiction_with_attributed_positions_passes() -> None:
    report = _report_with_contradictions(
        [
            Contradiction(
                topic="growth direction",
                positions=[
                    ContradictionPosition(statement="s1 reports growth", source_ids=["s1"]),
                    ContradictionPosition(statement="s2 reports decline", source_ids=["s2"]),
                ],
            )
        ],
        sources=[_source("s1"), _source("s2")],
    )
    validate_scribe_report(report)


def test_empty_contradictions_list_passes() -> None:
    section = _section("sec1", body_md='<span data-claim="sec1.c1">a[^s1]</span>')
    validate_scribe_report(_report([section]))


def test_contradiction_with_unknown_source_id_raises() -> None:
    report = _report_with_contradictions(
        [
            Contradiction(
                topic="conflict",
                positions=[
                    ContradictionPosition(statement="x", source_ids=["s1"]),
                    ContradictionPosition(statement="y", source_ids=["s99"]),
                ],
            )
        ],
        sources=[_source("s1"), _source("s2")],
    )
    with pytest.raises(ScribeValidationError, match="s99"):
        validate_scribe_report(report)


def test_contradiction_with_fewer_than_two_positions_raises() -> None:
    report = _report_with_contradictions(
        [
            Contradiction(
                topic="conflict",
                positions=[ContradictionPosition(statement="only one side", source_ids=["s1"])],
            )
        ],
        sources=[_source("s1"), _source("s2")],
    )
    with pytest.raises(ScribeValidationError, match=">= 2 positions"):
        validate_scribe_report(report)


def test_contradiction_position_without_sources_raises() -> None:
    report = _report_with_contradictions(
        [
            Contradiction(
                topic="conflict",
                positions=[
                    ContradictionPosition(statement="x", source_ids=["s1"]),
                    ContradictionPosition(statement="y", source_ids=[]),
                ],
            )
        ],
        sources=[_source("s1"), _source("s2")],
    )
    with pytest.raises(ScribeValidationError, match="at least one source"):
        validate_scribe_report(report)


def test_source_on_two_positions_raises() -> None:
    """A single source cannot hold both sides of a disagreement."""
    report = _report_with_contradictions(
        [
            Contradiction(
                topic="conflict",
                positions=[
                    ContradictionPosition(statement="x", source_ids=["s1"]),
                    ContradictionPosition(statement="y", source_ids=["s1"]),
                ],
            )
        ],
        sources=[_source("s1"), _source("s2")],
    )
    with pytest.raises(ScribeValidationError, match="more than one position"):
        validate_scribe_report(report)


# ---- critic validation -----------------------------------------------------


def _two_section_report() -> ScribeReport:
    return _report(
        [
            _section("sec1", body_md='<span data-claim="sec1.c1">a[^s1]</span>'),
            _section("sec2", body_md='<span data-claim="sec2.c1">b[^s2]</span>'),
        ]
    )


def _flag(claim_id: str, section_id: str, sources: list[str] | None = None) -> ClaimFlag:
    return ClaimFlag(
        claim_id=claim_id,
        section_id=section_id,
        verdict=Verdict.SUPPORTED,
        rationale="ok",
        supporting_source_ids=sources or [],
    )


def test_critic_validation_passes_when_complete() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[
            _flag("sec1.c1", "sec1", ["s1"]),
            _flag("sec2.c1", "sec2", ["s2"]),
        ],
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
            SectionConfidence(section_id="sec2", score=0.7, reasoning="ok"),
        ],
    )
    validate_critic_annotations(annotations, report)


def test_critic_rejects_missing_claim_flag() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[_flag("sec1.c1", "sec1")],  # sec2.c1 missing
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
            SectionConfidence(section_id="sec2", score=0.7, reasoning="ok"),
        ],
    )
    with pytest.raises(CriticValidationError, match="missing claim_flags"):
        validate_critic_annotations(annotations, report)


def test_critic_rejects_unknown_claim_flag() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[
            _flag("sec1.c1", "sec1"),
            _flag("sec2.c1", "sec2"),
            _flag("sec3.c1", "sec3"),  # not in report
        ],
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
            SectionConfidence(section_id="sec2", score=0.7, reasoning="ok"),
        ],
    )
    with pytest.raises(CriticValidationError, match="unknown claim_flags"):
        validate_critic_annotations(annotations, report)


def test_critic_rejects_duplicate_claim_flag() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[
            _flag("sec1.c1", "sec1"),
            _flag("sec1.c1", "sec1"),  # dup
            _flag("sec2.c1", "sec2"),
        ],
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
            SectionConfidence(section_id="sec2", score=0.7, reasoning="ok"),
        ],
    )
    with pytest.raises(CriticValidationError, match="duplicate claim_flags"):
        validate_critic_annotations(annotations, report)


def test_critic_rejects_unknown_supporting_source() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[
            _flag("sec1.c1", "sec1", ["s99"]),
            _flag("sec2.c1", "sec2"),
        ],
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
            SectionConfidence(section_id="sec2", score=0.7, reasoning="ok"),
        ],
    )
    with pytest.raises(CriticValidationError, match="unknown sources"):
        validate_critic_annotations(annotations, report)


def test_critic_rejects_section_id_mismatch_with_claim_prefix() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[
            _flag("sec1.c1", "sec2"),  # claim prefix sec1, but section_id sec2
            _flag("sec2.c1", "sec2"),
        ],
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
            SectionConfidence(section_id="sec2", score=0.7, reasoning="ok"),
        ],
    )
    with pytest.raises(CriticValidationError, match="claim id prefix"):
        validate_critic_annotations(annotations, report)


def test_critic_rejects_missing_section_confidence() -> None:
    report = _two_section_report()
    annotations = _annotations(
        report,
        claim_flags=[
            _flag("sec1.c1", "sec1"),
            _flag("sec2.c1", "sec2"),
        ],
        section_confidence=[
            SectionConfidence(section_id="sec1", score=0.8, reasoning="ok"),
        ],
    )
    with pytest.raises(CriticValidationError, match="missing section_confidence"):
        validate_critic_annotations(annotations, report)
