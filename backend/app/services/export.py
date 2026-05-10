"""Export renderers for completed VerifiedReport objects.

`build_markdown` produces a clean .md file (spans stripped, flagged claims appended).
`build_html` renders a self-contained HTML document with verdict-decorated claim spans.
`render_pdf` will be added in a subsequent task.
"""
from __future__ import annotations

import asyncio
import html
import re

import weasyprint
from markdown_it import MarkdownIt

from app.models.research import ClaimFlag, ReportSection, Verdict, VerifiedReport

_SPAN_CLAIM_RE = re.compile(r'<span\s+data-claim="[^"]*">(.*?)</span>', re.DOTALL)
_FLAGGED_VERDICTS = {Verdict.UNSUPPORTED, Verdict.CONTRADICTED}


def _strip_claim_spans(text: str) -> str:
    """Remove <span data-claim="..."> wrappers, keeping the wrapped text."""
    return _SPAN_CLAIM_RE.sub(r"\1", text)


def _claims_appendix(
    claim_flags: list[ClaimFlag],
    sections: list[ReportSection],
) -> list[str]:
    """Return markdown lines for a ## Flagged Claims section, or an empty list if nothing is flagged."""
    flagged = [f for f in claim_flags if f.verdict in _FLAGGED_VERDICTS]
    if not flagged:
        return []
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
    return lines


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
        lines.extend(appendix)
    return "\n".join(lines)


_PDF_CSS = """\
body{font-family:'Liberation Serif',Georgia,serif;max-width:760px;margin:40px auto;\
font-size:13pt;line-height:1.7;color:#1a1a1a}
h1{font-size:22pt;margin-bottom:6pt}
h2{font-size:16pt;margin-top:22pt;padding-bottom:4pt;border-bottom:1pt solid #ccc}
sup,a{font-size:9pt}
span[data-verdict=supported]{background:#d4f0d4;border-radius:2px;padding:0 2px}
span[data-verdict=partially_supported]{background:#fff3cd;border-radius:2px;padding:0 2px}
span[data-verdict=unsupported]{background:#ffe0e0;text-decoration:underline wavy red;\
border-radius:2px;padding:0 2px}
span[data-verdict=contradicted]{background:#ffe0e0;text-decoration:line-through;\
border-radius:2px;padding:0 2px}
ol.sources{font-size:11pt;color:#555}
@page{margin:2cm}
"""


def _decorate_claim_spans(html: str, claim_flags: list[ClaimFlag]) -> str:
    """Inject data-verdict attributes into existing data-claim spans."""
    verdict_map = {f.claim_id: f.verdict.value for f in claim_flags}

    def _replace(m: re.Match[str]) -> str:
        claim_id = m.group(1)
        verdict = verdict_map.get(claim_id)
        if verdict is not None:
            return f'<span data-claim="{claim_id}" data-verdict="{verdict}"'
        return m.group(0)

    return re.sub(r'<span data-claim="([^"]+)"', _replace, html)


def _html_template(title: str, lang: str, body_html: str) -> str:
    return (
        f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n'
        f'<meta charset="utf-8"><title>{html.escape(title)}</title>\n'
        f"<style>{_PDF_CSS}</style>\n"
        f"</head>\n<body>\n{body_html}\n</body>\n</html>"
    )


def build_html(verified: VerifiedReport) -> str:
    """Render a VerifiedReport as a self-contained HTML document.

    Claim spans in body_md are preserved and decorated with data-verdict
    attributes so WeasyPrint can apply verdict-specific CSS.
    """
    r = verified.report
    md = MarkdownIt(options_update={"html": True})

    lines: list[str] = [f"# {r.title}", "", r.summary_md, ""]
    for section in r.sections:
        lines += [f"## {section.heading}", "", section.body_md, ""]

    lines += ["## Sources", ""]
    for i, src in enumerate(r.sources, start=1):
        lines.append(f"{i}. [{src.title}]({src.url})")
    lines.append("")

    appendix = _claims_appendix(verified.annotations.claim_flags, r.sections)
    if appendix:
        lines.extend(appendix)

    body_html = md.render("\n".join(lines))
    body_html = _decorate_claim_spans(body_html, verified.annotations.claim_flags)
    return _html_template(r.title, verified.job.language, body_html)


def _weasyprint_sync(html: str) -> bytes:
    # Standalone function (not a lambda) so asyncio.to_thread can reference it
    # by name and profilers can attribute CPU time correctly.
    result: bytes = weasyprint.HTML(string=html).write_pdf()
    return result


async def render_pdf(verified: VerifiedReport) -> bytes:
    """Render a VerifiedReport as PDF bytes.

    WeasyPrint is synchronous and CPU-bound; running it in a thread prevents it
    from blocking the uvicorn event loop during concurrent requests.
    """
    html = build_html(verified)
    return await asyncio.to_thread(_weasyprint_sync, html)
