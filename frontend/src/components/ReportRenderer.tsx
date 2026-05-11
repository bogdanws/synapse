import { createContext, useContext, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema, type Options as SanitizeSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'

import type { ClaimFlag, ReportSection, Source, Verdict } from '../types/api'
import { credibilityColorOnInverse, extractDomain } from '../lib/source-utils'
import { Tooltip } from './ui/Tooltip'
import { cn } from './ui/cn'

// `unsupported` and `contradicted` collapse to critic-red, matching the
// background-class collapse a few lines below so footnotes agree with the
// claim highlight they're nested in.
function verdictColor(verdict: Verdict): string {
  switch (verdict) {
    case 'supported':
      return 'var(--scout)'
    case 'partially_supported':
      return 'var(--scribe)'
    case 'unsupported':
    case 'contradicted':
      return 'var(--critic)'
  }
}

// Same mapping, but reaches for the inverse-surface variants. Used inside
// tooltip popups where the background is `--fg` and the page tokens would
// fall below AA against ivory in dark mode.
function verdictColorOnInverse(verdict: Verdict): string {
  switch (verdict) {
    case 'supported':
      return 'var(--scout-on-inverse)'
    case 'partially_supported':
      return 'var(--scribe-on-inverse)'
    case 'unsupported':
    case 'contradicted':
      return 'var(--critic-on-inverse)'
  }
}

// react-markdown's component overrides don't expose parent nodes, so the
// only clean way for a `<sup>` to learn its surrounding claim's verdict is
// via context provided by ClaimHighlight.
const ClaimVerdictContext = createContext<Verdict | null>(null)

/**
 * Allow-list for raw HTML in Scribe's markdown output. Scribe wraps every
 * verifiable claim in `<span data-claim="secN.cM">…</span>` so the Critic and
 * the renderer can correlate flags with claims; everything else (script
 * tags, event handlers, alternative tags) is stripped. Web-search content
 * fed to the LLM is untrusted, so without this gate `rehypeRaw` would render
 * any injected `<script>` or `onerror=…` attribute live in the user's
 * browser. The schema starts from GitHub's defaults and only extends `span`
 * and `sup` to permit `data-*` (encoded as the `'data*'` wildcard per
 * `hast-util-sanitize`).
 */
const claimSpanSchema: SanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span ?? []), 'data*'],
    sup: [...(defaultSchema.attributes?.sup ?? []), 'data*'],
  },
}

interface ClaimHighlightProps {
  id: string
  flag: ClaimFlag | undefined
  children?: React.ReactNode
}

function ClaimHighlight({ id, flag, children }: ClaimHighlightProps) {
  if (!flag) {
    return <span data-claim={id}>{children}</span>
  }

  const bgClass =
    flag.verdict === 'supported'
      ? 'bg-scout-soft'
      : flag.verdict === 'partially_supported'
        ? 'bg-scribe-soft'
        : 'bg-critic-soft'

  const isContradicted = flag.verdict === 'contradicted'
  // Tooltip accent matches the inline highlight so the eye doesn't have to
  // re-map agent identity between the underline color and the popup label —
  // but uses the inverse-surface variant since the popup is `bg-fg`.
  const accent = verdictColorOnInverse(flag.verdict)

  const tooltipContent = (
    <div className="flex flex-col gap-1.5 normal-case tracking-normal py-0.5 max-w-[260px]">
      <div className="flex items-center gap-1.5">
        <span
          className="inline-block w-1 h-1 rounded-full"
          style={{ background: accent }}
          aria-hidden
        />
        <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: accent }}>
          {flag.verdict.replace(/_/g, ' ')}
        </span>
      </div>
      <div className="font-serif text-[13px] leading-snug text-bg/95">{flag.rationale}</div>
    </div>
  )

  return (
    <Tooltip content={tooltipContent} className="border-none shadow-xl px-3 py-2">
      <span
        data-claim={id}
        className={cn('px-0.5', bgClass, isContradicted && 'line-through')}
        style={isContradicted ? { color: 'var(--critic)' } : undefined}
      >
        <ClaimVerdictContext.Provider value={flag.verdict}>{children}</ClaimVerdictContext.Provider>
      </span>
    </Tooltip>
  )
}

interface FootnoteProps {
  source: Source
  label: string
  onSourceClick?: (id: string) => void
}

function Footnote({ source, label, onSourceClick }: FootnoteProps) {
  const domain = extractDomain(source.url)
  const verdict = useContext(ClaimVerdictContext)
  // Outside a flagged claim, fall back to muted rather than borrowing
  // source credibility — those are different signals.
  const color = verdict ? verdictColor(verdict) : 'var(--muted)'
  // Footnote tooltip lives on `bg-fg`, so reach for the inverse-surface
  // variant — `credibilityColor` is for chips on the page background.
  const credColor = credibilityColorOnInverse(source.credibility)
  const tooltipContent = (
    <div className="flex flex-col gap-2 normal-case tracking-normal py-0.5 max-w-[260px] text-bg">
      <div className="font-serif text-[13px] leading-snug text-bg/95">{source.title}</div>
      <div className="border-t border-bg/15 pt-1.5 flex items-center gap-2">
        <span className="font-mono text-[9px] text-bg/60 uppercase tracking-widest truncate">
          {domain}
        </span>
        <span className="w-px h-2 bg-bg/20 shrink-0" />
        <span
          className="font-mono text-[9px] uppercase tracking-widest shrink-0"
          style={{ color: credColor }}
        >
          Cred .{(source.credibility * 100).toFixed(0)}
        </span>
      </div>
    </div>
  )

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    if (onSourceClick) {
      onSourceClick(source.id)
    } else {
      const target = document.getElementById(source.id)
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' })
        window.history.pushState(null, '', `#${source.id}`)
      }
    }
  }

  return (
    <Tooltip content={tooltipContent} className="border-none shadow-xl px-3 py-2">
      <a
        href={`#${source.id}`}
        onClick={handleClick}
        className="inline-block px-0.5 font-mono text-[10px] font-bold no-underline transition-opacity hover:opacity-70"
        style={{ color }}
      >
        [{label}]
      </a>
    </Tooltip>
  )
}

interface ReportRendererProps {
  section: ReportSection
  claimFlags: ClaimFlag[]
  sources: Source[]
  onSourceClick?: (id: string) => void
}

export function ReportRenderer({
  section,
  claimFlags,
  sources,
  onSourceClick,
}: ReportRendererProps) {
  // O(1) lookup for footnotes — rebuilt only when the source list changes.
  const sourceMap = useMemo(() => {
    const map = new Map<string, Source>()
    for (const s of sources) {
      map.set(s.id, s)
    }
    return map
  }, [sources])

  // Scribe produces raw [^sX] syntax. Pre-process to wrap in <sup data-source="sX">
  const bodyWithFootnotes = section.body_md.replace(/\[\^(s\d+)\]/g, (_match, id) => {
    const num = id.replace('s', '')
    return `<sup data-source="${id}">${num}</sup>`
  })

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      // Order matters: rehypeRaw turns embedded HTML strings into HAST nodes
      // first, then rehypeSanitize prunes anything outside the allow-list.
      rehypePlugins={[rehypeRaw, [rehypeSanitize, claimSpanSchema]]}
      components={{
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        span: ({ node, ...props }: any) => {
          const claimId = node?.properties?.dataClaim as string | undefined
          if (claimId) {
            const flag = claimFlags.find((f) => f.claim_id === claimId)
            return <ClaimHighlight id={claimId} flag={flag} {...props} />
          }
          return <span {...props} />
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        sup: ({ node, children, ...props }: any) => {
          const sourceId = node?.properties?.dataSource as string | undefined
          if (sourceId) {
            const source = sourceMap.get(sourceId)
            if (!source) return <sup {...props}>{children}</sup>
            return (
              <sup>
                <Footnote source={source} label={String(children)} onSourceClick={onSourceClick} />
              </sup>
            )
          }
          return <sup {...props}>{children}</sup>
        },
      }}
    >
      {bodyWithFootnotes}
    </ReactMarkdown>
  )
}
