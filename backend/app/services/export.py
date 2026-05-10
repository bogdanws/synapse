"""Export renderers for completed VerifiedReport objects.

`build_markdown` produces a clean .md file (spans stripped, flagged claims appended).
`build_html` and `render_pdf` will be added in subsequent tasks.
"""
from __future__ import annotations

import re

from app.models.research import ClaimFlag, ReportSection, Verdict, VerifiedReport

_SPAN_CLAIM_RE = re.compile(r'<span\s+data-claim="[^"]*">(.*?)</span>', re.DOTALL)
_FLAGGED_VERDICTS = {Verdict.UNSUPPORTED, Verdict.CONTRADICTED}


def _strip_claim_spans(text: str) -> str:
    """Remove <span data-claim="..."> wrappers, keeping the wrapped text."""
    return _SPAN_CLAIM_RE.sub(r"\1", text)


def _claims_appendix(
    claim_flags: list[ClaimFlag],
    sections: list[ReportSection],
) -> str:
    """Return a markdown ## Flagged Claims section, or empty string if nothing is flagged."""
    flagged = [f for f in claim_flags if f.verdict in _FLAGGED_VERDICTS]
    if not flagged:
        return ""
    heading_by_id = {s.id: s.heading for s in sections}
    lines: list[str] = [
        "---",
        "",
        "## Flagged Claims",
        "",
        "The following claims were flagged as unsupported or contradicted by Critic.",
        "",
    ]
    for flag in flagged:
        heading = heading_by_id.get(flag.section_id, flag.section_id)
        lines += [
            f"**{flag.claim_id}** · *{heading}* · `{flag.verdict.value}`",
            f"> {flag.rationale}",
            "",
        ]
    return "\n".join(lines)


def build_markdown(verified: VerifiedReport) -> str:
    """Render a VerifiedReport as clean Markdown.

    Claim spans are stripped (footnote refs they contain remain). An appendix
    of unsupported/contradicted claims is appended when any exist.
    """
    r = verified.report
    lines: list[str] = [
        f"# {r.title}",
        "",
        _strip_claim_spans(r.summary_md),
        "",
    ]
    for section in r.sections:
        lines += [
            f"## {section.heading}",
            "",
            _strip_claim_spans(section.body_md),
            "",
        ]
    lines += ["## Sources", ""]
    for i, src in enumerate(r.sources, start=1):
        lines.append(f"[{i}] [{src.title}]({src.url})")
    lines.append("")
    appendix = _claims_appendix(verified.annotations.claim_flags, r.sections)
    if appendix:
        lines.append(appendix)
    return "\n".join(lines)
