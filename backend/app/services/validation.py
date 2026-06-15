"""Structural validators for Scribe and Critic outputs.

Pydantic catches type errors for free. These validators enforce the cross-field invariants Pydantic can't express:

  * Section IDs are `sec1`, `sec2`, … sequential and unique.
  * Inside each section's `body_md`, every `<span data-claim="…">` uses the
    section's id as prefix and the claim suffix (`c1`, `c2`, …) is sequential
    starting at 1, with each claim id appearing exactly once.
  * Every `[^sX]` or `[sX]` footnote reference resolves to a `Source.id` declared on
    the report — the only direction that catches genuine hallucination
    (referencing a source that does not exist) rather than redundant data
    the model could be asked to maintain.
  * Every footnote reference sits *inside* a `<span data-claim>` span. A citation
    outside any claim span is an "orphan" the Critic can never attach a verdict
    to, so the whole section ends up unverifiable. Catching it here turns a
    silently claim-less report into an actionable retry for the Scribe.
  * Each `Contradiction` in `report.contradictions` has >= 2 positions; every
    position cites at least one known `Source.id`; and no source appears on more
    than one side (the positions are mutually exclusive). An empty contradictions
    list is valid.

`ReportSection.cited_source_ids` is intentionally not validated here: it is derived from `body_md` by a model_validator on the section itself, so it cannot disagree with the prose.

A regex-based pass over the markdown is enough for these checks; the format is small and we do not need to interpret the document, only inspect a handful of inline patterns. Switching to a full markdown-it AST would buy more thorough span detection but no extra invariant coverage.
"""

from __future__ import annotations

import re

from app.models.research import (
    ClaimFlag,
    Contradiction,
    CriticAnnotations,
    ReportSection,
    ScribeReport,
)

# `<span data-claim="…">` openers. We accept any whitespace between the tag name and the attribute, single or double quotes, and ignore other attributes; the strict shape is enforced by the LLM prompt.
_CLAIM_SPAN_RE = re.compile(
    r"<span\b[^>]*\bdata-claim\s*=\s*['\"]([^'\"]+)['\"][^>]*>",
    re.IGNORECASE,
)
# Whole `<span data-claim="…">…</span>` blocks, including the wrapped text. Used to subtract claim regions from the body so we can spot footnote refs left outside any span. Non-greedy so adjacent spans don't merge; DOTALL so a span may wrap text spanning newlines.
_CLAIM_SPAN_BLOCK_RE = re.compile(
    r"<span\b[^>]*\bdata-claim\s*=\s*['\"][^'\"]+['\"][^>]*>.*?</span>",
    re.IGNORECASE | re.DOTALL,
)
# Footnote references like `[^s12]`; `[s12]` is accepted because models sometimes omit the caret. Markdown footnote definitions look the same followed by a colon (`[^s12]:`); we treat both as references for the purpose of "does this id appear in the body".
_FOOTNOTE_REF_RE = re.compile(r"\[\^?(s\d+)\]")
# A footnote *reference* in prose, distinct from a definition (`[^s12]:`). Only references must live inside claim spans; a definition — if a model ever emits one — is bibliography-like and legitimately sits outside spans, so the orphan check ignores it via the trailing-colon negative lookahead.
_FOOTNOTE_REF_IN_PROSE_RE = re.compile(r"\[\^?(s\d+)\](?!\s*:)")
_SECTION_ID_RE = re.compile(r"^sec(\d+)$")
_CLAIM_LOCAL_RE = re.compile(r"^c(\d+)$")

# Any `<span …>`/`</span>` tag. Used to strip claim markup out of the executive
# summary, which renders as plain text and so must not carry the body's
# span/citation convention.
_SPAN_TAG_RE = re.compile(r"</?span\b[^>]*>", re.IGNORECASE)
# Whitespace left dangling in front of punctuation after a citation is removed
# (e.g. "Council [^s2]." -> "Council ." -> "Council.").
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([.,;:!?])")

# Opening `<span data-claim="…">` tag split into (prefix)(id)(suffix) so the
# repair pass can rewrite just the id while leaving any other attributes intact.
_CLAIM_ATTR_RE = re.compile(
    r"(<span\b[^>]*\bdata-claim\s*=\s*['\"])([^'\"]+)(['\"][^>]*>)",
    re.IGNORECASE,
)
# Regions the orphan-citation repair must never reach into: fenced code blocks
# and inline code. A `[^sX]`-looking token inside code is not a citation.
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
# Leading block markup on a line (blockquote markers, list bullet, ordered-list
# number, ATX heading) that should sit *outside* a wrapped claim span.
_LEAD_MARKER_RE = re.compile(r"^[ \t]*(?:>[ \t]*)*(?:[-*+][ \t]+|\d+[.)][ \t]+|#{1,6}[ \t]+)?")
# End of a sentence: terminal punctuation, an optional closing quote/bracket,
# then whitespace. Used to find where the clause containing an orphan citation
# begins so we wrap the sentence rather than the whole paragraph.
_SENTENCE_END_RE = re.compile(r"[.!?][\"')\]]?[ \t]+")
_WORD_RE = re.compile(r"[A-Za-z0-9]")


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
    _validate_contradictions(report.contradictions, source_ids)


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


def strip_summary_markup(summary_md: str) -> str:
    """Remove claim spans and footnote citations from an executive summary.

    The summary renders as standalone prose, not alongside the source list, so a
    `<span data-claim>` wrapper or a `[^sX]` reference has nothing to resolve
    against and shows up as literal noise. Models nonetheless carry the body's
    citation convention into the summary, so we strip it here rather than trust
    the prompt alone: unwrap any span (keeping its text) and drop footnote refs,
    then tidy the whitespace the removals leave behind.

    Markdown emphasis, links, and the like are intentionally preserved — the
    field is GFM and only the claim/citation markup is out of place.
    """
    text = _FOOTNOTE_REF_RE.sub("", summary_md)
    text = _SPAN_TAG_RE.sub("", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def repair_orphan_citations(body_md: str, section_id: str) -> str:
    """Wrap orphan footnote citations in claim spans so a section can satisfy the Scribe contract.

    The single most common Scribe failure is a real citation for a real claim
    that the model simply forgot to wrap: a bare `[^sX]` sitting in prose
    outside any `<span data-claim>`. Unlike a hallucinated source id or a
    non-sequential section id, that is a *markup* slip, not a content error, and
    is mechanically fixable. We do the wrap server-side here instead of bouncing
    the whole job back to the model and hoping a weaker model gets it right on
    the (single) retry.

    For each orphan citation — or run of adjacent citations like `[^s4][^s7]` —
    this wraps the sentence containing it in a claim span, then renumbers every
    claim id in the section so the `c1, c2, …` sequencing invariant still holds
    after the insertion. It is deliberately conservative: it leaves the body
    untouched when there is nothing to repair (so it never perturbs an otherwise
    valid section or masks an unrelated validation error), and it bails on any
    citation whose surrounding context is risky to rewrite — tables, code, or
    text that would overlap an existing span. Anything it declines to fix still
    flows through to `validate_scribe_report`, which fails the section as before.

    Idempotent: running it on already-repaired prose is a no-op.
    """
    protected = _protected_spans(body_md)
    orphans = [
        m for m in _FOOTNOTE_REF_IN_PROSE_RE.finditer(body_md) if not _within(m.start(), protected)
    ]
    if not orphans:
        return body_md

    groups = _group_adjacent(body_md, orphans)
    edits: list[tuple[int, int]] = []
    for group_start, group_end in groups:
        region = _claim_region(body_md, group_start, group_end, protected)
        if region is not None:
            edits.append(region)

    if not edits:
        return body_md

    wrapped = _wrap_regions(body_md, edits, section_id)
    return _renumber_claims(wrapped, section_id)


# ---- internals --------------------------------------------------------------


def _protected_spans(body_md: str) -> list[tuple[int, int]]:
    """Character intervals the repair must not split: claim spans and code."""
    intervals = [(m.start(), m.end()) for m in _CLAIM_SPAN_BLOCK_RE.finditer(body_md)]
    intervals += [(m.start(), m.end()) for m in _FENCED_CODE_RE.finditer(body_md)]
    intervals += [(m.start(), m.end()) for m in _INLINE_CODE_RE.finditer(body_md)]
    intervals.sort()
    return intervals


def _within(pos: int, intervals: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in intervals)


def _group_adjacent(body_md: str, matches: list[re.Match[str]]) -> list[tuple[int, int]]:
    """Merge citations separated only by spaces (`[^s4][^s7]`) into one claim."""
    groups: list[tuple[int, int]] = []
    for match in matches:
        if groups and body_md[groups[-1][1] : match.start()].strip(" \t") == "":
            groups[-1] = (groups[-1][0], match.end())
        else:
            groups.append((match.start(), match.end()))
    return groups


def _claim_region(
    body_md: str,
    group_start: int,
    group_end: int,
    protected: list[tuple[int, int]],
) -> tuple[int, int] | None:
    """Find the span `[start, group_end)` to wrap, or `None` if unsafe to repair.

    The wrap covers the sentence on the citation's own line, minus any leading
    block markup (bullets, headings). Returns `None` rather than guess when the
    line looks like a table, or the claim text would overlap an existing span.
    """
    line_start = body_md.rfind("\n", 0, group_start) + 1
    lead = _LEAD_MARKER_RE.match(body_md, line_start, group_start)
    lead_start = lead.end() if lead else line_start

    sentence_start = lead_start
    last_end: re.Match[str] | None = None
    for match in _SENTENCE_END_RE.finditer(body_md, lead_start, group_start):
        last_end = match
    if last_end is not None and _WORD_RE.search(body_md, last_end.end(), group_start):
        # Only cut to the sentence boundary if real words remain after it;
        # otherwise the citation trails a finished sentence and we keep the line.
        sentence_start = last_end.end()
    text_start = sentence_start

    for start, end in protected:
        if start < group_end and end > text_start:
            if end <= group_start:
                text_start = max(text_start, end)
            else:
                # A protected region overlaps the claim text we'd wrap.
                return None

    region = body_md[text_start:group_start]
    if "|" in region or "\n" in region:
        return None
    return (text_start, group_end)


def _wrap_regions(body_md: str, edits: list[tuple[int, int]], section_id: str) -> str:
    """Insert claim spans around each region. Ids are placeholders; see renumber."""
    parts: list[str] = []
    cursor = 0
    for start, end in sorted(edits):
        parts.append(body_md[cursor:start])
        parts.append(f'<span data-claim="{section_id}.c0">')
        parts.append(body_md[start:end])
        parts.append("</span>")
        cursor = end
    parts.append(body_md[cursor:])
    return "".join(parts)


def _renumber_claims(body_md: str, section_id: str) -> str:
    """Rewrite every claim id to `<section_id>.c<n>` in document order.

    Run only after an insertion: re-sequencing in document order is what keeps
    the `c1, c2, …` invariant intact once a new span lands mid-body. Skipping it
    when nothing was inserted is deliberate — we must not silently fix claim-id
    mistakes the model made on its own, which the validator should still surface.
    """
    counter = iter(range(1, 1_000_000))

    def _rewrite(match: re.Match[str]) -> str:
        return f"{match.group(1)}{section_id}.c{next(counter)}{match.group(3)}"

    return _CLAIM_ATTR_RE.sub(_rewrite, body_md)


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


def _validate_contradictions(contradictions: list[Contradiction], source_ids: set[str]) -> None:
    for i, contradiction in enumerate(contradictions):
        label = f"contradiction #{i + 1}"
        if len(contradiction.positions) < 2:
            msg = f"{label}: must have >= 2 positions (got {len(contradiction.positions)})"
            raise ScribeValidationError(msg)

        # A source may appear at most once across all positions: a single source
        # cannot simultaneously hold two contradicting sides.
        seen_sources: set[str] = set()
        for j, position in enumerate(contradiction.positions, start=1):
            if not position.source_ids:
                msg = f"{label}, position #{j}: must cite at least one source"
                raise ScribeValidationError(msg)

            unknown = set(position.source_ids) - source_ids
            if unknown:
                msg = (
                    f"{label}, position #{j}: source_ids {sorted(unknown)} "
                    f"do not match any Source.id"
                )
                raise ScribeValidationError(msg)

            overlap = seen_sources.intersection(position.source_ids)
            if overlap:
                msg = (
                    f"{label}: source_ids {sorted(overlap)} appear on more than one "
                    f"position; each source may hold only one side"
                )
                raise ScribeValidationError(msg)
            seen_sources.update(position.source_ids)


def _validate_footnote_refs(section: ReportSection, source_ids: set[str]) -> None:
    refs = set(_FOOTNOTE_REF_RE.findall(section.body_md))
    unknown = refs - source_ids
    if unknown:
        msg = f"section {section.id}: footnote refs {sorted(unknown)} do not match any Source.id"
        raise ScribeValidationError(msg)

    outside_spans = _CLAIM_SPAN_BLOCK_RE.sub("", section.body_md)
    orphans = sorted(set(_FOOTNOTE_REF_IN_PROSE_RE.findall(outside_spans)))
    if orphans:
        msg = (
            f"section {section.id}: footnote refs {orphans} appear outside a "
            f"<span data-claim> span; wrap each cited claim in a span"
        )
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
