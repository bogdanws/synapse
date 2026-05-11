import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema, type Options as SanitizeSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'

import type { ClaimFlag, ReportSection, Source } from '../types/api'
import { Tooltip } from './ui/Tooltip'
import { cn } from './ui/cn'

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

  const tooltipContent = (
    <span>
      <span
        className="uppercase tracking-widest"
        style={{ color: isContradicted ? 'var(--critic)' : undefined }}
      >
        {flag.verdict.replace(/_/g, ' ')}
      </span>
      {' — '}
      {flag.rationale}
    </span>
  )

  return (
    <Tooltip content={tooltipContent}>
      <span
        data-claim={id}
        className={cn('px-0.5', bgClass, isContradicted && 'line-through')}
        style={isContradicted ? { color: 'var(--critic)' } : undefined}
      >
        {children}
      </span>
    </Tooltip>
  )
}

interface FootnoteProps {
  sourceId: string
  sources: Source[]
  label: string
}

function Footnote({ sourceId, sources, label }: FootnoteProps) {
  const source = sources.find((s) => s.id === sourceId)
  if (!source) return <sup>{label}</sup>

  const domain = new URL(source.url).hostname.replace(/^www\./, '')
  const tooltipContent = (
    <div className="flex flex-col gap-1 normal-case tracking-normal py-0.5 text-bg">
      <div className="font-serif text-[13px] leading-tight">{source.title}</div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className="font-mono text-[9px] text-bg/70 uppercase tracking-widest">{domain}</span>
        <span className="w-px h-2 bg-bg/20" />
        <span className="font-mono text-[9px] text-scout uppercase tracking-widest">
          Cred .{(source.credibility * 100).toFixed(0)}
        </span>
      </div>
    </div>
  )

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    const target = document.getElementById(sourceId)
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Update hash without jumping immediately (since we handled scroll)
      window.history.pushState(null, '', `#${sourceId}`)
    }
  }

  return (
    <Tooltip content={tooltipContent} className="bg-fg text-bg border-none shadow-xl lowercase">
      <a
        href={`#${sourceId}`}
        onClick={handleClick}
        className="inline-block px-0.5 -mt-2 font-mono text-[10px] font-bold text-scout hover:text-scout/80 no-underline"
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
}

export function ReportRenderer({ section, claimFlags, sources }: ReportRendererProps) {
  // Scribe produces raw [^sX] syntax. Pre-process to wrap in <sup data-source="sX">
  const bodyWithFootnotes = section.body_md.replace(/\[\^(s\d+)\]/g, (match, id) => {
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
            return (
              <Footnote sourceId={sourceId} sources={sources} label={String(children)} />
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
