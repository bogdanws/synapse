"""Scribe — synthesis agent.

Turns a topic plus Scout's curated sources into a structured `ScribeReport`. Makes one structured-output LLM call; if the resulting report violates the format contract, it retries once with the validation error appended to the prompt before giving up.

We keep the LLM's output schema narrower than `ScribeReport`: the model returns only the parts it actually generates (title, summary, sections, contradictions, follow-ups). Fields that the system already knows — `id`, `job_id`, `topic`, `sources`, `generated_at`, `model` — are attached server-side. This prevents the model from dropping or inventing sources, which would in turn break Critic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from app.models.research import (
    Contradiction,
    ReportSection,
    ScribeReport,
    Source,
)
from app.services.llm import build_chat_model
from app.services.validation import ScribeValidationError, validate_scribe_report

_log = structlog.get_logger(__name__)

# One initial attempt plus this many retries on validation failure. Keep small: each retry roughly doubles the cost and wall time, and a model that fails twice rarely recovers on a third try.
_MAX_VALIDATION_RETRIES = 1

_SYSTEM_PROMPT = """\
You are a research synthesist. Given a topic, a list of sub-questions, and a curated set of web sources, write a structured, cited report.

Output format
-------------
Return strictly valid JSON matching this shape (no commentary, no markdown fence):

{
  "title": "<short title>",
  "summary_md": "<executive summary in GFM markdown, 2-4 sentences>",
  "sections": [
    {
      "id": "sec1",
      "heading": "<section heading>",
      "body_md": "<GFM markdown body>",
      "cited_source_ids": ["s1", "s3", ...]
    },
    ...
  ],
  "contradictions": [
    { "description": "<one-sentence summary>", "source_ids": ["sX", "sY"] }
  ],
  "follow_ups": ["<follow-up question>", ...]
}

Section rules
-------------
- Section ids are sequential: sec1, sec2, sec3, ... (no gaps).
- Aim for 3-6 sections with descriptive headings.

Claim wrapping (mandatory)
--------------------------
Every factual claim that could be checked against a source must be wrapped in:

    <span data-claim="<section_id>.c<n>">…claim text…</span>

Within each section, claim suffixes start at c1 and increment by one (c1, c2, c3, ...). The section_id prefix must match the section's own id. This is the only HTML allowed in body_md.

Citations
---------
Cite sources with footnotes [^sX] where X is the source's short id (s1, s2, ...). Place the citation inside the relevant <span data-claim>. Every id listed in a section's cited_source_ids must appear at least once as a [^sX] footnote in that section's body_md.

Tables, blockquotes, and lists use standard GFM. Do not invent sources. Only cite ids that appear in the input list.
"""


class _ScribeLLMOutput(BaseModel):
    title: str
    summary_md: str
    sections: list[ReportSection]
    contradictions: list[Contradiction]
    follow_ups: list[str]


class ScribeAgent:
    def __init__(self, model: str) -> None:
        self.model = model

    async def synthesize(
        self,
        *,
        job_id: UUID,
        topic: str,
        sub_questions: list[str],
        sources: list[Source],
    ) -> ScribeReport:
        """Generate a validated `ScribeReport` from sources.

        Raises `ScribeValidationError` if the model produces an invalid report after all retries.
        """
        if not sources:
            # An empty source list is a legitimate Scout outcome (e.g. all
            # results filtered out). We surface it explicitly here rather than
            # letting the LLM hallucinate sources from nothing.
            msg = "cannot synthesize a report with no sources"
            raise ScribeValidationError(msg)

        last_error: str | None = None
        for attempt in range(_MAX_VALIDATION_RETRIES + 1):
            llm_output = await self._call_llm(
                topic=topic,
                sub_questions=sub_questions,
                sources=sources,
                retry_feedback=last_error,
            )
            report = self._assemble(
                job_id=job_id,
                topic=topic,
                sources=sources,
                llm_output=llm_output,
            )
            try:
                validate_scribe_report(report)
            except ScribeValidationError as exc:
                last_error = str(exc)
                _log.warning(
                    "scribe_validation_failed",
                    attempt=attempt + 1,
                    error=last_error,
                )
                continue
            return report

        msg = f"scribe output failed validation after {_MAX_VALIDATION_RETRIES + 1} attempts: {last_error}"
        raise ScribeValidationError(msg)

    async def _call_llm(
        self,
        *,
        topic: str,
        sub_questions: list[str],
        sources: list[Source],
        retry_feedback: str | None,
    ) -> _ScribeLLMOutput:
        chat = build_chat_model(self.model).with_structured_output(
            _ScribeLLMOutput,
            method="json_mode",
        )
        user_msg = _build_user_prompt(topic, sub_questions, sources, retry_feedback)
        result = await chat.ainvoke(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]
        )
        if not isinstance(result, _ScribeLLMOutput):
            msg = f"unexpected scribe response type: {type(result)!r}"
            raise TypeError(msg)
        return result

    def _assemble(
        self,
        *,
        job_id: UUID,
        topic: str,
        sources: list[Source],
        llm_output: _ScribeLLMOutput,
    ) -> ScribeReport:
        return ScribeReport(
            id=uuid4(),
            job_id=job_id,
            topic=topic,
            title=llm_output.title,
            summary_md=llm_output.summary_md,
            sections=llm_output.sections,
            sources=sources,
            contradictions=llm_output.contradictions,
            follow_ups=llm_output.follow_ups,
            generated_at=datetime.now(UTC),
            model=self.model,
        )


def _build_user_prompt(
    topic: str,
    sub_questions: list[str],
    sources: list[Source],
    retry_feedback: str | None,
) -> str:
    sub_q_block = "\n".join(f"- {q}" for q in sub_questions) or "(none)"
    source_block = "\n\n".join(
        (f"[{src.id}] {src.title}\nURL: {src.url}\nSnippet: {src.snippet}") for src in sources
    )
    parts = [
        f"Topic: {topic}",
        f"Sub-questions:\n{sub_q_block}",
        f"Sources:\n{source_block}",
    ]
    if retry_feedback:
        # Surfaced verbatim so the model gets actionable structural feedback rather than a generic "try again".
        parts.append(
            "Your previous response failed validation with this error:\n"
            f"{retry_feedback}\n"
            "Fix the issue and resubmit a fully valid report."
        )
    return "\n\n".join(parts)
