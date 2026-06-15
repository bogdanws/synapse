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
    repair_orphan_citations,
    strip_summary_markup,
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


# ---- orphan-citation repair ------------------------------------------------


def _repaired_report(body_md: str, *, sources: list[Source] | None = None) -> ScribeReport:
    """Repair a single-section body and assemble it into a report.

    Mirrors what `ScribeAgent._assemble` does: repair runs before the section is
    constructed, so the section's derived `cited_source_ids` and the validator
    both see the repaired prose.
    """
    repaired = repair_orphan_citations(body_md, "sec1")
    return _report([_section("sec1", body_md=repaired)], sources=sources)


def test_repair_wraps_section_of_only_orphan_citations() -> None:
    """The exact production failure: prose with citations, no spans."""
    body = "DeepSeek V4 Pro was released under an MIT license[^s1][^s2]."
    report = _repaired_report(body)
    section = report.sections[0]
    assert "outside" not in section.body_md  # sanity: no leftover prose ref
    # Both adjacent citations are pulled into one claim span.
    assert '<span data-claim="sec1.c1">' in section.body_md
    assert "[^s1][^s2]" in section.body_md
    assert section.cited_source_ids == ["s1", "s2"]
    validate_scribe_report(report)  # must not raise


def test_repair_wraps_only_the_orphan_and_keeps_existing_spans() -> None:
    body = (
        'Wrapped <span data-claim="sec1.c1">claim[^s1]</span>. '
        "But this fact is cited outside any span[^s2]."
    )
    report = _repaired_report(body)
    section = report.sections[0]
    # The pre-existing span survives and the orphan gains its own span; claims
    # are renumbered sequentially in document order.
    assert section.body_md.count("data-claim") == 2
    assert '<span data-claim="sec1.c1">claim[^s1]</span>' in section.body_md
    assert '<span data-claim="sec1.c2">' in section.body_md
    assert "any span[^s2]" in section.body_md
    validate_scribe_report(report)


def test_repair_renumbers_when_inserting_before_existing_span() -> None:
    """An orphan ahead of an existing claim forces a full, ordered renumber."""
    body = 'Bare lead citation[^s1]. Then <span data-claim="sec1.c1">a wrapped claim[^s2]</span>.'
    report = _repaired_report(body)
    section = report.sections[0]
    # Document order is orphan-first, so it becomes c1 and the old c1 becomes c2.
    first = section.body_md.index('data-claim="sec1.c1"')
    second = section.body_md.index('data-claim="sec1.c2"')
    assert first < second
    assert "lead citation[^s1]" in section.body_md[first:second]
    validate_scribe_report(report)


def test_repair_is_noop_without_orphans() -> None:
    body = '<span data-claim="sec1.c1">a[^s1]</span>'
    assert repair_orphan_citations(body, "sec1") == body


def test_repair_is_idempotent() -> None:
    body = "An unwrapped factual claim[^s1]."
    once = repair_orphan_citations(body, "sec1")
    twice = repair_orphan_citations(once, "sec1")
    assert once == twice


def test_repair_leaves_footnote_definitions_alone() -> None:
    body = '<span data-claim="sec1.c1">claim[^s1]</span>\n\n[^s1]: A source.\n'
    assert repair_orphan_citations(body, "sec1") == body


def test_repair_skips_table_rows() -> None:
    """A `|`-bearing line is likely a table; wrapping it could corrupt the cell."""
    body = "| Model | Source |\n| --- | --- |\n| DeepSeek | cited[^s1] |"
    # Nothing safe to wrap, so the body is returned unchanged and the validator
    # still surfaces the orphan rather than the repair silently mangling a table.
    assert repair_orphan_citations(body, "sec1") == body
    with pytest.raises(ScribeValidationError, match="outside a <span data-claim> span"):
        validate_scribe_report(_report([_section("sec1", body_md=body)]))


def test_repair_skips_citations_inside_code() -> None:
    body = "Use the token `[^s1]` literally in code."
    assert repair_orphan_citations(body, "sec1") == body


def test_repair_wraps_per_sentence_not_whole_paragraph() -> None:
    body = "First sentence is plain. Second makes a claim[^s1]."
    repaired = repair_orphan_citations(body, "sec1")
    assert repaired.startswith("First sentence is plain. ")
    assert '<span data-claim="sec1.c1">Second makes a claim[^s1]</span>' in repaired


def test_repair_strips_leading_list_marker_from_claim() -> None:
    body = "- A bulleted finding[^s1]"
    repaired = repair_orphan_citations(body, "sec1")
    # The bullet marker stays outside the span; only the claim text is wrapped.
    assert repaired.startswith("- <span data-claim=")
    validate_scribe_report(_report([_section("sec1", body_md=repaired)]))


# ---- summary markup stripping ----------------------------------------------


def test_strip_summary_removes_spans_and_citations() -> None:
    """Regression: the model carried body claim markup into the plain-text summary."""
    summary = (
        "As of June 15, 2026, Romania is in a transitional phase. "
        '<span data-claim="summary.c1">Adrian Veștea was designated PM on June 14, '
        "2026[^s2]</span>, following a resignation. "
        '<span data-claim="summary.c2">Veștea is vice-president of the PNL[^s2]</span>.'
    )
    result = strip_summary_markup(summary)
    assert "<span" not in result
    assert "</span>" not in result
    assert "[^s2]" not in result
    assert "data-claim" not in result
    # Prose and punctuation survive cleanly.
    assert result == (
        "As of June 15, 2026, Romania is in a transitional phase. "
        "Adrian Veștea was designated PM on June 14, 2026, following a resignation. "
        "Veștea is vice-president of the PNL."
    )


def test_strip_summary_tidies_space_left_before_punctuation() -> None:
    assert strip_summary_markup("The council met [^s2].") == "The council met."


def test_strip_summary_preserves_plain_markdown() -> None:
    summary = "Growth was **strong** and [steady](https://example.com)."
    assert strip_summary_markup(summary) == summary


def test_strip_summary_is_noop_on_clean_prose() -> None:
    summary = "A concise, citation-free executive summary."
    assert strip_summary_markup(summary) == summary
