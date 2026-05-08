import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema, type Options as SanitizeSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'

import type { ClaimFlag, ReportSection } from '../types/api'
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
 * to permit `data-*` (encoded as the `'data*'` wildcard per
 * `hast-util-sanitize`).
 */
const claimSpanSchema: SanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span ?? []), 'data*'],
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

interface ReportRendererProps {
  section: ReportSection
  claimFlags: ClaimFlag[]
}

export function ReportRenderer({ section, claimFlags }: ReportRendererProps) {
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
      }}
    >
      {section.body_md}
    </ReactMarkdown>
  )
}
