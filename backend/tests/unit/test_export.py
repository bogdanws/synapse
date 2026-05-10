"""Unit tests for app/services/export.py — markdown builder."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from app.models.research import (
    ClaimFlag,
    CriticAnnotations,
    Depth,
    JobStatus,
    ReportSection,
    ResearchJob,
    ScribeReport,
    SectionConfidence,
    Source,
    Verdict,
    VerifiedReport,
)
from app.services.export import build_html, build_markdown, render_pdf

_NOW = datetime.now(UTC)
_JOB_ID = uuid4()
_REPORT_ID = uuid4()
_ANNOTATION_ID = uuid4()
_VALID_MODELS = {"scout": "m", "scribe": "m", "critic": "m"}


def _make_verified(
    *,
    body_md: str = 'Claim text <span data-claim="sec1.c1">with citation[^s1]</span>.',
    summary_md: str = 'Summary <span data-claim="sec0.c1">text[^s1]</span>.',
    verdict: Verdict = Verdict.SUPPORTED,
) -> VerifiedReport:
    job = ResearchJob(
        id=_JOB_ID,
        topic="Test topic",
        language="en",
        depth=Depth.STANDARD,
        models=_VALID_MODELS,
        status=JobStatus.COMPLETED,
        progress=1.0,
        created_at=_NOW,
        updated_at=_NOW,
    )
    section = ReportSection(id="sec1", heading="Section One", body_md=body_md)
    source = Source(
        id="s1",
        url="https://example.com",  # type: ignore[arg-type]
        title="Example Source",
        credibility=0.9,
        relevance=0.85,
        snippet="snippet text",
    )
    report = ScribeReport(
        id=_REPORT_ID,
        job_id=_JOB_ID,
        topic="Test topic",
        title="Test Report Title",
        summary_md=summary_md,
        sections=[section],
        sources=[source],
        contradictions=[],
        follow_ups=[],
        generated_at=_NOW,
        model="test/model",
    )
    annotations = CriticAnnotations(
        id=_ANNOTATION_ID,
        report_id=_REPORT_ID,
        section_confidence=[SectionConfidence(section_id="sec1", score=0.9, reasoning="ok")],
        claim_flags=[
            ClaimFlag(
                claim_id="sec1.c1",
                section_id="sec1",
                verdict=verdict,
                rationale="Test rationale.",
                supporting_source_ids=["s1"],
            )
        ],
        overall_confidence=0.9,
        model="test/model",
        generated_at=_NOW,
    )
    return VerifiedReport(job=job, report=report, annotations=annotations)


def test_build_markdown_strips_spans_from_body() -> None:
    verified = _make_verified()
    md = build_markdown(verified)
    assert "<span" not in md
    assert "with citation" in md


def test_build_markdown_strips_spans_from_summary() -> None:
    verified = _make_verified()
    md = build_markdown(verified)
    assert "Summary text[^s1]." in md
    assert "<span" not in md


def test_build_markdown_contains_h1_title() -> None:
    verified = _make_verified()
    md = build_markdown(verified)
    assert "# Test Report Title" in md


def test_build_markdown_contains_section_heading() -> None:
    verified = _make_verified()
    md = build_markdown(verified)
    assert "## Section One" in md


def test_build_markdown_contains_source_entry() -> None:
    verified = _make_verified()
    md = build_markdown(verified)
    assert "Example Source" in md
    assert "https://example.com" in md


def test_build_markdown_appends_flagged_claims_for_unsupported() -> None:
    verified = _make_verified(verdict=Verdict.UNSUPPORTED)
    md = build_markdown(verified)
    assert "## Flagged Claims" in md
    assert "sec1.c1" in md
    assert "Test rationale." in md


def test_build_markdown_appends_flagged_claims_for_contradicted() -> None:
    verified = _make_verified(verdict=Verdict.CONTRADICTED)
    md = build_markdown(verified)
    assert "## Flagged Claims" in md


def test_build_markdown_no_appendix_when_all_supported() -> None:
    verified = _make_verified(verdict=Verdict.SUPPORTED)
    md = build_markdown(verified)
    assert "## Flagged Claims" not in md


def test_build_markdown_no_appendix_when_partially_supported() -> None:
    verified = _make_verified(verdict=Verdict.PARTIALLY_SUPPORTED)
    md = build_markdown(verified)
    assert "## Flagged Claims" not in md


def test_build_html_is_valid_html_document() -> None:
    verified = _make_verified()
    html = build_html(verified)
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html


def test_build_html_embeds_title() -> None:
    verified = _make_verified()
    html = build_html(verified)
    assert "Test Report Title" in html


def test_build_html_includes_verdict_css() -> None:
    verified = _make_verified()
    html = build_html(verified)
    assert "data-verdict=supported" in html
    assert "data-verdict=unsupported" in html
    assert "data-verdict=partially_supported" in html
    assert "data-verdict=contradicted" in html


def test_build_html_decorates_unsupported_span() -> None:
    verified = _make_verified(verdict=Verdict.UNSUPPORTED)
    html = build_html(verified)
    assert 'data-verdict="unsupported"' in html


def test_build_html_decorates_supported_span() -> None:
    verified = _make_verified(verdict=Verdict.SUPPORTED)
    html = build_html(verified)
    assert 'data-verdict="supported"' in html


def test_build_html_preserves_claim_span_text() -> None:
    verified = _make_verified()
    html = build_html(verified)
    assert "with citation" in html


def test_build_html_contains_source_list() -> None:
    verified = _make_verified()
    html = build_html(verified)
    assert "Example Source" in html


async def test_render_pdf_calls_weasyprint_with_html_string() -> None:
    verified = _make_verified()
    fake_pdf = b"%PDF-fake"

    with patch("app.services.export.weasyprint") as mock_wp:
        mock_wp.HTML.return_value.write_pdf.return_value = fake_pdf
        result = await render_pdf(verified)

    assert result == fake_pdf
    call_kwargs = mock_wp.HTML.call_args.kwargs
    assert "<!DOCTYPE html>" in call_kwargs["string"]
    mock_wp.HTML.return_value.write_pdf.assert_called_once()


async def test_render_pdf_returns_bytes() -> None:
    verified = _make_verified()
    fake_pdf = b"%PDF-1.4 fake content"

    with patch("app.services.export.weasyprint") as mock_wp:
        mock_wp.HTML.return_value.write_pdf.return_value = fake_pdf
        result = await render_pdf(verified)

    assert isinstance(result, bytes)
    assert result == fake_pdf
