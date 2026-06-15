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
    dated_system_prompt,
    invoke_structured_with_retry,
)
from app.services.validation import (
    ScribeValidationError,
    repair_orphan_citations,
    strip_summary_markup,
    validate_scribe_report,
)

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
  "summary_md": "<executive summary, plain GFM prose, 2-4 sentences — no claim spans, no citations>",
  "sections": [
    {
      "id": "sec1",
      "heading": "<section heading>",
      "body_md": "<GFM markdown body — see Body rules below>"
    },
    ...
  ],
  "contradictions": [
    {
      "topic": "<short label for the point of disagreement>",
      "positions": [
        { "statement": "<what these sources claim>", "source_ids": ["sX"] },
        { "statement": "<the conflicting claim>", "source_ids": ["sY"] }
      ]
    }
  ],
  "follow_ups": ["<follow-up question>", ...]
}

Field rules
-----------
- `summary_md`: plain prose only. It renders on its own, away from the sources, so it must contain **no** `<span data-claim>` wrappers and **no** `[^sX]` citations — those belong solely in section bodies. Save the evidence for the sections.
- `id`: sequential `sec1`, `sec2`, `sec3`, ... with no gaps. Aim for 3-6 sections with descriptive headings.
- `contradictions`: record only genuine factual disagreements. Each entry names the disputed `topic` and splits it into >= 2 **positions** — each a short `statement` of what one side claims plus the `source_ids` advancing it. A source may appear on **only one** position; never put the same id on two sides, and never invent ids. Use an **empty array** when sources do not conflict.

Body rules (mandatory — most failures come from skipping these)
---------------------------------------------------------------
1. Every factual claim that could be checked against a source must be wrapped in a span tag:

       <span data-claim="<section_id>.c<n>">...claim text [^sX]...</span>

   Be thorough: most substantive sections should contain at least one such claim. Prefer concrete, sourced statements over vague generalities, and wrap each one. A section with zero claims is only appropriate when it is genuinely non-factual (e.g. a short framing or transition).

2. The `section_id` prefix MUST match the section's own `id`.
3. Claim suffixes start at `c1` and increment by one within each section (`c1`, `c2`, `c3`, ...) — no gaps, no duplicates. (WRONG: `sec1.c1` then `sec1.c3`. RIGHT: `sec1.c1` then `sec1.c2`.)
4. Every citation `[^sX]` MUST appear inside one of these spans — this is the single most common failure. A bare `[^sX]` sitting in ordinary prose is invalid; wrap the whole sentence that makes the claim. Use the exact short id from the input source list; never invent a new id.

       WRONG (citation left outside any span):
           The Hubble constant is roughly 70 km/s/Mpc[^s3].
       RIGHT (the claiming sentence is wrapped):
           <span data-claim="sec1.c1">The Hubble constant is roughly 70 km/s/Mpc[^s3]</span>.

5. The span tag is the only HTML allowed in `body_md`. Tables, blockquotes, and lists use standard GFM.

Worked example of one section's `body_md`:

    The market grew 12% YoY in Q4 <span data-claim="sec1.c1">according to the industry report[^s2]</span>. Adoption was uneven across regions, <span data-claim="sec1.c2">with EMEA leading[^s4][^s7]</span>.

Worked example of one `contradictions` entry (note the two sides are attributed to *different* sources):

    {
      "topic": "Q4 market growth rate",
      "positions": [
        { "statement": "The market grew 12% year over year.", "source_ids": ["s2"] },
        { "statement": "Growth was flat, under 2% year over year.", "source_ids": ["s4"] }
      ]
    }

The same entry done WRONG — `s2` appears on both sides; one source cannot hold two contradicting positions, so this is rejected:

    {
      "topic": "Q4 market growth rate",
      "positions": [
        { "statement": "The market grew 12% year over year.", "source_ids": ["s2"] },
        { "statement": "Growth was flat, under 2% year over year.", "source_ids": ["s2"] }
      ]
    }

Do not invent sources. Only cite ids that appear in the input list.
"""


class _LLMReportSection(BaseModel):
    """Section shape the model emits.

    Narrower than `ReportSection`: omits `cited_source_ids`, which is derived server-side from `body_md` after the call. Asking the model to maintain that field in lockstep with its own prose was a frequent retry trigger and added nothing the renderer or critic couldn't get from the footnote refs themselves.
    """

    id: str
    heading: str
    body_md: str


class _ScribeLLMOutput(BaseModel):
    title: str
    summary_md: str
    sections: list[_LLMReportSection]
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
            {"role": "system", "content": dated_system_prompt(_SYSTEM_PROMPT)},
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
        # Repair orphan citations before anything else reads the body: a bare
        # `[^sX]` the model forgot to wrap is the dominant Scribe failure and is
        # mechanically fixable, so we wrap it here rather than fail the job. The
        # pass is a no-op when there is nothing to repair, so it never masks an
        # unrelated validation error. `cited_source_ids` is then derived from the
        # repaired `body_md` by `ReportSection`'s model_validator.
        sections = [
            ReportSection(
                id=s.id,
                heading=s.heading,
                body_md=repair_orphan_citations(s.body_md, s.id),
            )
            for s in llm_output.sections
        ]
        return ScribeReport(
            id=uuid4(),
            job_id=job_id,
            topic=topic,
            title=llm_output.title,
            # The summary renders as plain prose; strip any claim spans or
            # citations the model carried over from the body convention.
            summary_md=strip_summary_markup(llm_output.summary_md),
            sections=sections,
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
    hint = ""
    if "outside a <span data-claim>" in error:
        # The server already repairs most orphan citations; if one still reaches
        # the model, spell out the mechanical fix so a weaker model can apply it.
        hint = (
            "\n\nFor each [^sX] listed above: find the sentence containing it and "
            'wrap that sentence in <span data-claim="secN.cM">…</span>, keeping the '
            "claim numbering sequential within the section. Every [^sX] in the body "
            "must end up inside exactly one claim span."
        )
    return (
        "Your previous response failed validation with this error:\n"
        f"{error}\n\n"
        "Reply with a fully corrected report in the same JSON shape. "
        "Preserve the parts that were correct; change only what the error references."
        f"{hint}"
    )
