"""Export renderers for completed VerifiedReport objects.

`build_markdown` produces a clean .md file (spans stripped, flagged claims appended).
`build_html` renders a self-contained HTML document with verdict-decorated claim spans.
`render_pdf` renders a PDF document from the HTML representation of the report.
"""

from __future__ import annotations

import asyncio
import html
import re

import weasyprint
from markdown_it import MarkdownIt

from app.models.research import ClaimFlag, ReportSection, Verdict, VerifiedReport

_SPAN_CLAIM_RE = re.compile(
    r"<span\b[^>]*\bdata-claim\s*=\s*['\"][^'\"]+['\"][^>]*>(.*?)</span>",
    re.DOTALL,
)
_FOOTNOTE_REF_RE = re.compile(r"\[\^(s\d+)\]")
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
        "The following claims were flagged as unsupported or contradicted.",
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
:root {
  --ivory:       #F5F1E8;
  --ivory-2:     #EDE8DC;
  --ink:         #0F0F0E;
  --muted:       #6B675E;
  --rule:        #C9C2B0;
  --scout:       #3F72B0;
  --scout-soft:  #E8EEF6;
  --scribe-soft: #F5F0D5;
  --critic:      #A85428;
  --critic-soft: #F8E7DC;
  --serif: "Liberation Serif", Georgia, "Times New Roman", serif;
  --mono:  "Liberation Mono", "Courier New", Courier, monospace;
}

@page {
  size: A4;
  margin: 2cm;
  background: #FFFFFF;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: var(--mono);
    font-size: 8pt;
    letter-spacing: 0.08em;
    color: var(--muted);
  }
}

html, body {
  background: #FFFFFF;
  color: var(--ink);
  font-family: var(--serif);
  font-size: 12pt;
  line-height: 1.65;
  margin: 0;
}

.masthead {
  padding-bottom: 18pt;
  border-bottom: 1.5pt solid var(--ink);
  margin-bottom: 24pt;
}

.micro {
  font-family: var(--mono);
  font-size: 8pt;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 8pt 0;
}

h1 {
  font-family: var(--serif);
  font-size: 34pt;
  font-weight: 400;
  line-height: 1.05;
  letter-spacing: -0.025em;
  margin: 0;
  color: var(--ink);
}

.summary {
  background: var(--ivory-2);
  padding: 16pt 20pt;
  margin-bottom: 24pt;
  border-left: 2pt solid var(--ink);
}

.summary .micro { margin-bottom: 6pt; }

.summary p {
  font-size: 14pt;
  line-height: 1.5;
  letter-spacing: -0.005em;
  margin: 0;
}

h2 {
  font-family: var(--serif);
  font-size: 20pt;
  font-weight: 400;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--ink);
  margin: 24pt 0 8pt 0;
  padding-top: 14pt;
  border-top: 0.5pt solid var(--rule);
}

.section-num {
  font-family: var(--mono);
  font-size: 9pt;
  color: var(--muted);
  margin-right: 6pt;
}

p { font-size: 12pt; line-height: 1.65; margin: 0 0 9pt 0; }

blockquote {
  border-left: 2pt solid var(--rule);
  padding-left: 12pt;
  color: var(--muted);
  margin: 0 0 9pt 0;
  font-style: italic;
}

ol, ul { font-size: 12pt; line-height: 1.55; padding-left: 18pt; margin: 0 0 9pt 0; }

sup { font-family: var(--mono); font-size: 8pt; }

a { color: var(--scout); text-decoration: none; }

span[data-verdict=supported] {
  background: var(--scout-soft);
  border-radius: 2px;
  padding: 0 2px;
}

span[data-verdict=partially_supported] {
  background: var(--scribe-soft);
  border-radius: 2px;
  padding: 0 2px;
}

span[data-verdict=unsupported] {
  background: var(--critic-soft);
  border-bottom: 1pt dashed var(--critic);
  padding: 0 2px;
}

span[data-verdict=contradicted] {
  color: var(--critic);
  text-decoration: line-through;
  padding: 0 2px;
}

.sources {
  margin-top: 24pt;
  padding-top: 14pt;
  border-top: 1.5pt solid var(--ink);
}

.sources ol { font-size: 10pt; line-height: 1.55; color: var(--muted); margin-top: 8pt; }

.sources li { padding-bottom: 3pt; }

.appendix {
  margin-top: 24pt;
  padding-top: 14pt;
  border-top: 1.5pt solid var(--ink);
}

.appendix h2 {
  border-top: none;
  padding-top: 0;
  margin-top: 0;
  font-size: 16pt;
}

.appendix-desc {
  color: var(--muted);
  font-style: italic;
  margin-bottom: 14pt;
  font-size: 11pt;
}

.flagged-claim {
  border-left: 2pt solid var(--critic);
  padding: 6pt 0 6pt 12pt;
  margin-bottom: 10pt;
}

.flagged-claim-header {
  font-family: var(--mono);
  font-size: 8pt;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--critic);
  margin-bottom: 4pt;
}

.flagged-claim-rationale { font-style: italic; color: #3A3833; font-size: 11pt; }

hr { border: none; border-top: 0.5pt solid var(--rule); margin: 20pt 0; }

/* ── Page-break controls ── */

/* Keep heading paired with at least its first line of body; the section itself
   may still break freely across pages so content flows rather than jumping. */
h1, h2 { break-after: avoid; }

/* Small atomic blocks that look wrong if split across a page boundary. */
.masthead  { break-inside: avoid; }
.summary   { break-inside: avoid; }
.flagged-claim { break-inside: avoid; }
li         { break-inside: avoid; }

/* Orphan/widow control: require at least 3 lines at the start and end of
   every page fragment so a lone line is never stranded. */
p { orphans: 3; widows: 3; }
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


def _linkify_footnote_refs(body: str, source_url_map: dict[str, str]) -> str:
    """Replace [^sN] markers with superscript PDF hyperlinks to the source URL.

    markdown-it-py does not process footnote syntax without a plugin, so refs
    survive as literal [^sN] text in the rendered HTML. WeasyPrint encodes
    <a href> elements as PDF link annotations (no resource fetch occurs), so
    each number becomes clickable in any PDF viewer.
    """

    def _replace(m: re.Match[str]) -> str:
        src_id = m.group(1)
        url = source_url_map.get(src_id)
        if url is None:
            return m.group(0)
        return f'<sup><a href="{html.escape(url)}">{src_id[1:]}</a></sup>'

    return _FOOTNOTE_REF_RE.sub(_replace, body)


def _html_template(title: str, lang: str, body_html: str) -> str:
    return (
        f'<!DOCTYPE html>\n<html lang="{html.escape(lang)}">\n<head>\n'
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
    parts: list[str] = []

    parts += [
        '<header class="masthead">',
        f"<h1>{html.escape(r.title)}</h1>",
        "</header>",
    ]

    parts += [
        '<div class="summary">',
        '<p class="micro">Executive Summary</p>',
        md.render(r.summary_md),
        "</div>",
    ]

    for i, section in enumerate(r.sections, 1):
        parts += [
            '<section class="report-section">',
            f'<h2><span class="section-num">§ {i}</span> {html.escape(section.heading)}</h2>',
            md.render(section.body_md),
            "</section>",
        ]

    parts += ['<section class="sources">', '<p class="micro">Sources</p>', "<ol>"]
    for src in r.sources:
        parts.append(f'<li><a href="{html.escape(str(src.url))}">{html.escape(src.title)}</a></li>')
    parts += ["</ol>", "</section>"]

    flagged = [f for f in verified.annotations.claim_flags if f.verdict in _FLAGGED_VERDICTS]
    if flagged:
        heading_by_id = {s.id: s.heading for s in r.sections}
        parts += [
            '<section class="appendix">',
            "<h2>Flagged Claims</h2>",
            '<p class="appendix-desc">The following claims were flagged as unsupported or contradicted.</p>',
        ]
        for flag in flagged:
            section_label = html.escape(heading_by_id.get(flag.section_id, flag.section_id))
            parts += [
                '<div class="flagged-claim">',
                f'<div class="flagged-claim-header">'
                f"{html.escape(flag.claim_id)} · {section_label}"
                f" · {html.escape(flag.verdict.value)}</div>",
                f'<div class="flagged-claim-rationale">{html.escape(flag.rationale)}</div>',
                "</div>",
            ]
        parts.append("</section>")

    source_url_map = {src.id: str(src.url) for src in r.sources}
    body_html = "\n".join(parts)
    body_html = _decorate_claim_spans(body_html, verified.annotations.claim_flags)
    body_html = _linkify_footnote_refs(body_html, source_url_map)
    return _html_template(r.title, verified.job.language, body_html)


def _deny_url_fetcher(url: str, timeout: int = 10, ssl_cert_files: object = None) -> None:
    # The generated HTML is self-contained; any URL reference in report content
    # (LLM-produced) must not be fetched during PDF rendering to prevent SSRF.
    raise ValueError(f"External resource fetch denied during PDF export: {url}")


def _weasyprint_sync(html: str) -> bytes:
    # Standalone function (not a lambda) so asyncio.to_thread can reference it
    # by name and profilers can attribute CPU time correctly.
    result = weasyprint.HTML(string=html, url_fetcher=_deny_url_fetcher).write_pdf()
    assert result is not None  # only None when a target path is passed; we don't
    return result


async def render_pdf(verified: VerifiedReport) -> bytes:
    """Render a VerifiedReport as PDF bytes.

    WeasyPrint is synchronous and CPU-bound; running it in a thread prevents it
    from blocking the uvicorn event loop during concurrent requests.
    """
    html = build_html(verified)
    return await asyncio.to_thread(_weasyprint_sync, html)
