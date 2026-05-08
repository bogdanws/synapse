"""Critic — fact-checking agent.

Verifies a `ScribeReport` claim-by-claim against the original sources. One LLM call per section, parallelisable; per-section output is light-validated and retried once on failure, then the per-section results are aggregated and the whole `CriticAnnotations` is run through the global validator before being returned.

The agent stays free of pubsub plumbing — `app.agents.critic_graph` wraps it for the LangGraph node and emits `ClaimVerified` events as each section completes.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

import structlog
from pydantic import BaseModel

from app.models.research import (
    ClaimFlag,
    CriticAnnotations,
    ReportSection,
    ScribeReport,
    SectionConfidence,
    Source,
)
from app.services.llm import build_chat_model
from app.services.validation import (
    CriticValidationError,
    validate_critic_annotations,
)

_log = structlog.get_logger(__name__)

_MAX_VALIDATION_RETRIES = 1

# Same regex as the Scribe validator. Duplicated here rather than imported because the validation module's pattern is intentionally module-private — exposing a public alias would invite drift in either direction.
_CLAIM_SPAN_RE = re.compile(
    r"<span\b[^>]*\bdata-claim\s*=\s*['\"]([^'\"]+)['\"][^>]*>",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """\
You are a fact-checker. You will be given one section of a research report (in markdown, with each verifiable claim wrapped in `<span data-claim="...">...</span>`) plus the full pool of sources cited anywhere in the report.

Your job is to:

1. For every `<span data-claim="<claim_id>">…</span>` in the section, return one entry in `claim_flags` with:
   - `claim_id`: exactly the id from the span.
   - `section_id`: the section id passed in (always equals the prefix of `claim_id`).
   - `verdict`: one of `supported`, `partially_supported`, `unsupported`, `contradicted`.
   - `rationale`: at most three sentences justifying the verdict.
   - `supporting_source_ids`: list of source short-ids (`s1`, `s2`, …) that support the claim. Empty when the verdict is `unsupported`.
2. Return a single `section_confidence` for the section with:
   - `section_id`: the section id passed in.
   - `score`: a float in [0, 1] reflecting your confidence that the section's claims are well-sourced overall.
   - `reasoning`: at most three sentences.

Constraints:

- Output strictly valid JSON — no commentary, no markdown fences.
- Cover every claim id present in the section. No extras, no duplicates.
- Only cite source ids that appear in the input list.
"""


class _CriticSectionOutput(BaseModel):
    """Per-section LLM output. Aggregated across sections to form `CriticAnnotations`."""

    section_confidence: SectionConfidence
    claim_flags: list[ClaimFlag]


class CriticAgent:
    def __init__(self, model: str) -> None:
        self.model = model

    async def verify_section(
        self,
        *,
        topic: str,
        section: ReportSection,
        sources: list[Source],
    ) -> _CriticSectionOutput:
        """Run one LLM call to verify all claims in `section`. Retries once on validation failure."""
        source_ids = {s.id for s in sources}
        last_error: str | None = None
        for attempt in range(_MAX_VALIDATION_RETRIES + 1):
            output = await self._call_llm(
                topic=topic,
                section=section,
                sources=sources,
                retry_feedback=last_error,
            )
            try:
                _validate_section_output(output, section, source_ids)
            except CriticValidationError as exc:
                last_error = str(exc)
                _log.warning(
                    "critic_section_validation_failed",
                    section_id=section.id,
                    attempt=attempt + 1,
                    error=last_error,
                )
                continue
            return output
        msg = (
            f"critic output for section {section.id} failed validation "
            f"after {_MAX_VALIDATION_RETRIES + 1} attempts: {last_error}"
        )
        raise CriticValidationError(msg)

    def aggregate(
        self,
        report: ScribeReport,
        section_outputs: list[_CriticSectionOutput],
    ) -> CriticAnnotations:
        """Combine per-section outputs into a `CriticAnnotations` and run the global validator.

        `section_outputs` may arrive in any order (the node uses `asyncio.as_completed` to interleave events); we sort the aggregated lists by their declared section index so the persisted annotation is deterministic regardless of completion order.
        """
        section_index = {s.id: i for i, s in enumerate(report.sections)}
        confidences = sorted(
            (out.section_confidence for out in section_outputs),
            key=lambda c: section_index.get(c.section_id, len(section_index)),
        )
        flags = sorted(
            (flag for out in section_outputs for flag in out.claim_flags),
            key=lambda f: (
                section_index.get(f.section_id, len(section_index)),
                _claim_local_index(f.claim_id),
            ),
        )
        annotations = CriticAnnotations(
            id=uuid4(),
            report_id=report.id,
            section_confidence=confidences,
            claim_flags=flags,
            overall_confidence=_overall_confidence(confidences),
            model=self.model,
            generated_at=datetime.now(UTC),
        )
        validate_critic_annotations(annotations, report)
        return annotations

    async def _call_llm(
        self,
        *,
        topic: str,
        section: ReportSection,
        sources: list[Source],
        retry_feedback: str | None,
    ) -> _CriticSectionOutput:
        chat = build_chat_model(self.model).with_structured_output(
            _CriticSectionOutput,
            method="json_mode",
        )
        user_msg = _build_user_prompt(topic, section, sources, retry_feedback)
        result = await chat.ainvoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
        )
        if not isinstance(result, _CriticSectionOutput):
            msg = f"unexpected critic response type: {type(result)!r}"
            raise TypeError(msg)
        return result


# ---- helpers --------------------------------------------------------------


def _validate_section_output(
    output: _CriticSectionOutput,
    section: ReportSection,
    source_ids: set[str],
) -> None:
    """Lightweight per-section check.

    Catches the common modes of model misbehaviour at minimal cost so the retry loop has actionable feedback. The full cross-section invariants (uniqueness across the whole report, etc.) are handled by `validate_critic_annotations` after aggregation.
    """
    if output.section_confidence.section_id != section.id:
        msg = (
            f"section_confidence.section_id is {output.section_confidence.section_id!r}, "
            f"expected {section.id!r}"
        )
        raise CriticValidationError(msg)

    expected_claims = set(_CLAIM_SPAN_RE.findall(section.body_md))
    actual_claims = [f.claim_id for f in output.claim_flags]

    duplicates = _duplicates(actual_claims)
    if duplicates:
        msg = f"duplicate claim_flags for ids: {sorted(duplicates)}"
        raise CriticValidationError(msg)

    missing = expected_claims - set(actual_claims)
    if missing:
        msg = f"missing claim_flags for section {section.id}: {sorted(missing)}"
        raise CriticValidationError(msg)

    extras = set(actual_claims) - expected_claims
    if extras:
        msg = f"unknown claim_flags in section {section.id}: {sorted(extras)}"
        raise CriticValidationError(msg)

    for flag in output.claim_flags:
        if flag.section_id != section.id:
            msg = (
                f"flag {flag.claim_id!r} has section_id {flag.section_id!r}, "
                f"expected {section.id!r}"
            )
            raise CriticValidationError(msg)
        unknown = set(flag.supporting_source_ids) - source_ids
        if unknown:
            msg = f"flag {flag.claim_id!r} cites unknown sources: {sorted(unknown)}"
            raise CriticValidationError(msg)


def _build_user_prompt(
    topic: str,
    section: ReportSection,
    sources: list[Source],
    retry_feedback: str | None,
) -> str:
    source_block = "\n\n".join(
        f"[{src.id}] {src.title}\nURL: {src.url}\nSnippet: {src.snippet}" for src in sources
    )
    parts = [
        f"Topic: {topic}",
        f"Section id: {section.id}",
        f"Section heading: {section.heading}",
        f"Section body:\n{section.body_md}",
        f"Sources:\n{source_block}",
    ]
    if retry_feedback:
        parts.append(
            "Your previous response failed validation with this error:\n"
            f"{retry_feedback}\n"
            "Fix the issue and resubmit a fully valid response."
        )
    return "\n\n".join(parts)


def _overall_confidence(confidences: list[SectionConfidence]) -> float:
    if not confidences:
        return 0.0
    return round(sum(c.score for c in confidences) / len(confidences), 4)


def _claim_local_index(claim_id: str) -> int:
    """Sort key helper: extracts the trailing integer from a claim id like `sec2.c5`.

    Returns a large fallback value for malformed ids so they sort to the end without crashing aggregation; the global validator will then reject the malformed id.
    """
    _, _, local = claim_id.partition(".")
    if local.startswith("c") and local[1:].isdigit():
        return int(local[1:])
    return 1_000_000


def _duplicates(items: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for x in items:
        if x in seen:
            dupes.add(x)
        seen.add(x)
    return dupes
