import { ConfidenceBar } from './ConfidenceBar'
import { ReportRenderer } from './ReportRenderer'
import type {
  ClaimFlag,
  ReportSection as ReportSectionType,
  SectionConfidence,
  Source,
} from '../types/api'

interface ReportSectionProps {
  num: number
  section: ReportSectionType
  confidence: SectionConfidence | undefined
  claimFlags: ClaimFlag[]
  sources: Source[]
  onSourceClick?: (id: string) => void
}

export function ReportSection({
  num,
  section,
  confidence,
  claimFlags,
  sources,
  onSourceClick,
}: ReportSectionProps) {
  return (
    <section>
      <div className="flex items-baseline gap-4 mb-2">
        <span className="font-mono shrink-0" style={{ fontSize: 11, color: 'var(--muted)' }}>
          §{num}
        </span>
        <h2
          className="serif flex-1"
          style={{
            fontSize: 36,
            fontWeight: 400,
            letterSpacing: '-0.025em',
            margin: 0,
            lineHeight: 1.1,
          }}
        >
          {section.heading}
        </h2>
        {confidence && (
          <div className="flex items-center gap-2 shrink-0">
            <span className="micro">conf</span>
            <ConfidenceBar value={confidence.score} className="w-16" />
          </div>
        )}
      </div>
      <div
        className="serif"
        style={{
          fontSize: 16,
          lineHeight: 1.65,
          fontWeight: 300,
          color: 'var(--fg)',
          maxWidth: 680,
        }}
      >
        <ReportRenderer
          section={section}
          claimFlags={claimFlags}
          sources={sources}
          onSourceClick={onSourceClick}
        />
      </div>
    </section>
  )
}
