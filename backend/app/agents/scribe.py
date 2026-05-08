"""Scribe — synthesis agent.

Turns a topic plus Scout's curated sources into a structured `ScribeReport`. Makes one structured-output LLM call routed through `invoke_structured_with_retry`, which replays the model's previous (invalid) response back as an assistant turn on retry so the model can edit its mistake instead of starting over.

We keep the LLM's output schema narrower than `ScribeReport`: the model returns only the parts it actually generates (title, summary, sections, contradictions, follow-ups). Fields that the system already knows — `id`, `job_id`, `topic`, `sources`, `generated_at`, `model` — are attached server-side. This prevents the model from dropping or inventing sources, which would in turn break Critic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel

from app.models.research import (
    Contradiction,
    ReportSection,
    ScribeReport,
    Source,
)
from app.services.llm import (
    StructuredRetryError,
    build_chat_model,
    invoke_structured_with_retry,
)
from app.services.validation import ScribeValidationError, validate_scribe_report

_log = structlog.get_logger(__name__)

# One initial attempt plus this many retries on validation failure. Kept at one for cost reasons; the conversation-aware retry below means a single retry is meaningfully different from the initial attempt (the model sees its previous bad output), so this is more useful than it would be otherwise.
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
      "body_md": "<GFM markdown body — see Body rules below>",
      "cited_source_ids": ["s1", "s3", ...]
    },
    ...
  ],
  "contradictions": [
    { "description": "<one-sentence summary>", "source_ids": ["sX", "sY"] }
  ],
  "follow_ups": ["<follow-up question>", ...]
}

Field rules
-----------
- `id`: sequential `sec1`, `sec2`, `sec3`, ... with no gaps. Aim for 3-6 sections with descriptive headings.
- `cited_source_ids`: every id listed here MUST appear at least once as `[^sX]` inside that section's `body_md`. Conversely, do not list ids that aren't actually cited in the prose.

Body rules (mandatory — most failures come from skipping these)
---------------------------------------------------------------
1. Every factual claim that could be checked against a source must be wrapped in a span tag:

       <span data-claim="<section_id>.c<n>">...claim text [^sX]...</span>

2. The `section_id` prefix MUST match the section's own `id`.
3. Claim suffixes start at `c1` and increment by one within each section (`c1`, `c2`, `c3`, ...) — no gaps, no duplicates.
4. Every citation `[^sX]` MUST appear inside one of these spans. Use the exact short id from the input source list; never invent a new id.
5. The span tag is the only HTML allowed in `body_md`. Tables, blockquotes, and lists use standard GFM.

Worked example of one section's `body_md`:

    The market grew 12% YoY in Q4 <span data-claim="sec1.c1">according to the industry report[^s2]</span>. Adoption was uneven across regions, <span data-claim="sec1.c2">with EMEA leading[^s4][^s7]</span>.

with `cited_source_ids: ["s2", "s4", "s7"]`.

Do not invent sources. Only cite ids that appear in the input list.
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

        chat = build_chat_model(self.model).with_structured_output(
            _ScribeLLMOutput,
            method="json_mode",
            include_raw=True,
        )
        messages: list[Any] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_initial_prompt(topic, sub_questions, sources),
            },
        ]

        # Closure validator: assembling inside the validator lets `validate_scribe_report` see the final shape (with sources attached) and gives the helper a single error string per failed attempt. Re-assembly on success is cheap (just a Pydantic constructor) and keeps the validator pure.
        def _validate(parsed: _ScribeLLMOutput) -> None:
            candidate = self._assemble(
                job_id=job_id, topic=topic, sources=sources, llm_output=parsed
            )
            validate_scribe_report(candidate)

        try:
            parsed = await invoke_structured_with_retry(
                chat,
                messages,
                validate=_validate,
                retry_feedback=_retry_feedback_message,
                max_retries=_MAX_VALIDATION_RETRIES,
                log_event="scribe_validation_failed",
                log=_log,
            )
        except StructuredRetryError as exc:
            msg = f"scribe output failed validation after {exc.attempts} attempts: {exc.last_error}"
            raise ScribeValidationError(msg) from exc

        return self._assemble(job_id=job_id, topic=topic, sources=sources, llm_output=parsed)

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


def _build_initial_prompt(
    topic: str,
    sub_questions: list[str],
    sources: list[Source],
) -> str:
    sub_q_block = "\n".join(f"- {q}" for q in sub_questions) or "(none)"
    source_block = "\n\n".join(
        (f"[{src.id}] {src.title}\nURL: {src.url}\nSnippet: {src.snippet}") for src in sources
    )
    return "\n\n".join(
        [
            f"Topic: {topic}",
            f"Sub-questions:\n{sub_q_block}",
            f"Sources:\n{source_block}",
        ]
    )


def _retry_feedback_message(error: str) -> str:
    """Targeted feedback paired with the model's previous assistant turn.

    Phrased as an edit on the prior response (rather than "try again from scratch") because the prior response is now visible in the conversation history.
    """
    return (
        "Your previous response failed validation with this error:\n"
        f"{error}\n\n"
        "Reply with a fully corrected report in the same JSON shape. "
        "Preserve the parts that were correct; change only what the error references."
    )
