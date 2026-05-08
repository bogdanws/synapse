"""Structural validators for Scribe and Critic outputs.

Pydantic catches type errors for free. These validators enforce the cross-field invariants Pydantic can't express:

  * Section IDs are `sec1`, `sec2`, … sequential and unique.
  * Inside each section's `body_md`, every `<span data-claim="…">` uses the
    section's id as prefix and the claim suffix (`c1`, `c2`, …) is sequential
    starting at 1, with each claim id appearing exactly once.
  * Every `[^sX]` footnote reference resolves to a `Source.id` declared on
    the report — the only direction that catches genuine hallucination
    (referencing a source that does not exist) rather than redundant data
    the model could be asked to maintain.

`ReportSection.cited_source_ids` is intentionally not validated here: it is derived from `body_md` by a model_validator on the section itself, so it cannot disagree with the prose.

A regex-based pass over the markdown is enough for these checks; the format is small and we do not need to interpret the document, only inspect a handful of inline patterns. Switching to a full markdown-it AST would buy more thorough span detection but no extra invariant coverage.
"""

from __future__ import annotations

import re

from app.models.research import (
    ClaimFlag,
    CriticAnnotations,
    ReportSection,
    ScribeReport,
)

# `<span data-claim="…">` openers. We accept any whitespace between the tag name and the attribute, single or double quotes, and ignore other attributes; the strict shape is enforced by the LLM prompt.
_CLAIM_SPAN_RE = re.compile(
    r"<span\b[^>]*\bdata-claim\s*=\s*['\"]([^'\"]+)['\"][^>]*>",
    re.IGNORECASE,
)
# Footnote references like `[^s12]`. Markdown footnote definitions look the same followed by a colon (`[^s12]:`); we treat both as references for the purpose of "does this id appear in the body".
_FOOTNOTE_REF_RE = re.compile(r"\[\^(s\d+)\]")
_SECTION_ID_RE = re.compile(r"^sec(\d+)$")
_CLAIM_LOCAL_RE = re.compile(r"^c(\d+)$")


class ScribeValidationError(ValueError):
    """Raised when a Scribe report violates the structural contract.

    The retry loop in `ScribeAgent.synthesize` catches this and feeds the error message back to the model on the next attempt, so keep messages specific and actionable.
    """


class CriticValidationError(ValueError):
    """Raised when Critic annotations do not match their report."""


def validate_scribe_report(report: ScribeReport) -> None:
    """Enforce the Scribe output contract. Raises `ScribeValidationError` on the first failure."""
    _validate_section_ids(report.sections)
    source_ids = {s.id for s in report.sources}
    for index, section in enumerate(report.sections, start=1):
        expected_section_id = f"sec{index}"
        _validate_claim_spans(section, expected_section_id)
        _validate_footnote_refs(section, source_ids)


def validate_critic_annotations(annotations: CriticAnnotations, report: ScribeReport) -> None:
    """Enforce the Critic output contract against a known-good `ScribeReport`."""
    expected_claim_ids = _collect_claim_ids(report)
    actual_claim_ids = [f.claim_id for f in annotations.claim_flags]

    duplicates = _duplicates(actual_claim_ids)
    if duplicates:
        msg = f"duplicate claim_flags for ids: {sorted(duplicates)}"
        raise CriticValidationError(msg)

    missing = expected_claim_ids - set(actual_claim_ids)
    if missing:
        msg = f"missing claim_flags for ids: {sorted(missing)}"
        raise CriticValidationError(msg)

    extras = set(actual_claim_ids) - expected_claim_ids
    if extras:
        msg = f"unknown claim_flags for ids not in report: {sorted(extras)}"
        raise CriticValidationError(msg)

    expected_section_ids = {s.id for s in report.sections}
    actual_section_ids = [c.section_id for c in annotations.section_confidence]
    section_dupes = _duplicates(actual_section_ids)
    if section_dupes:
        msg = f"duplicate section_confidence entries for: {sorted(section_dupes)}"
        raise CriticValidationError(msg)

    missing_sections = expected_section_ids - set(actual_section_ids)
    if missing_sections:
        msg = f"missing section_confidence entries for: {sorted(missing_sections)}"
        raise CriticValidationError(msg)

    extra_sections = set(actual_section_ids) - expected_section_ids
    if extra_sections:
        msg = f"unknown section_confidence entries for: {sorted(extra_sections)}"
        raise CriticValidationError(msg)

    source_ids = {s.id for s in report.sources}
    for flag in annotations.claim_flags:
        unknown = set(flag.supporting_source_ids) - source_ids
        if unknown:
            msg = f"flag for {flag.claim_id} cites unknown sources: {sorted(unknown)}"
            raise CriticValidationError(msg)
        _validate_flag_section_match(flag)


# ---- internals --------------------------------------------------------------


def _validate_section_ids(sections: list[ReportSection]) -> None:
    if not sections:
        msg = "report has no sections"
        raise ScribeValidationError(msg)
    for index, section in enumerate(sections, start=1):
        match = _SECTION_ID_RE.match(section.id)
        if match is None or int(match.group(1)) != index:
            msg = f"section #{index} has id {section.id!r}, expected 'sec{index}'"
            raise ScribeValidationError(msg)


def _validate_claim_spans(section: ReportSection, expected_section_id: str) -> None:
    claim_ids = _CLAIM_SPAN_RE.findall(section.body_md)
    seen: set[str] = set()
    expected_local = 1
    for claim_id in claim_ids:
        if "." not in claim_id:
            msg = f"section {section.id}: claim id {claim_id!r} is missing the section prefix"
            raise ScribeValidationError(msg)
        prefix, _, local = claim_id.partition(".")
        if prefix != expected_section_id:
            msg = (
                f"section {section.id}: claim id {claim_id!r} uses prefix {prefix!r} "
                f"but expected {expected_section_id!r}"
            )
            raise ScribeValidationError(msg)
        local_match = _CLAIM_LOCAL_RE.match(local)
        if local_match is None:
            msg = f"section {section.id}: claim id {claim_id!r} has malformed suffix"
            raise ScribeValidationError(msg)
        if claim_id in seen:
            msg = f"section {section.id}: claim id {claim_id!r} appears more than once"
            raise ScribeValidationError(msg)
        if int(local_match.group(1)) != expected_local:
            msg = (
                f"section {section.id}: expected next claim 'c{expected_local}', found {claim_id!r}"
            )
            raise ScribeValidationError(msg)
        seen.add(claim_id)
        expected_local += 1


def _validate_footnote_refs(section: ReportSection, source_ids: set[str]) -> None:
    refs = set(_FOOTNOTE_REF_RE.findall(section.body_md))
    unknown = refs - source_ids
    if unknown:
        msg = f"section {section.id}: footnote refs {sorted(unknown)} do not match any Source.id"
        raise ScribeValidationError(msg)


def _collect_claim_ids(report: ScribeReport) -> set[str]:
    ids: set[str] = set()
    for section in report.sections:
        ids.update(_CLAIM_SPAN_RE.findall(section.body_md))
    return ids


def _validate_flag_section_match(flag: ClaimFlag) -> None:
    prefix, _, _ = flag.claim_id.partition(".")
    if prefix != flag.section_id:
        msg = (
            f"flag {flag.claim_id!r} reports section_id {flag.section_id!r} "
            f"but the claim id prefix is {prefix!r}"
        )
        raise CriticValidationError(msg)


def _duplicates(items: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for x in items:
        if x in seen:
            dupes.add(x)
        seen.add(x)
    return dupes
