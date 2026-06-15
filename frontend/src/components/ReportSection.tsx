import { ReportRenderer } from './ReportRenderer'
import type { ClaimFlag, ReportSection as ReportSectionType, Source } from '../types/api'

interface ReportSectionProps {
  num: number
  section: ReportSectionType
  claimFlags: ClaimFlag[]
  sources: Source[]
  onSourceClick?: (id: string) => void
}

export function ReportSection({
  num,
  section,
  claimFlags,
  sources,
  onSourceClick,
}: ReportSectionProps) {
  return (
    <section>
      <div className="flex items-baseline gap-4 mb-2">
        <span className="font-mono shrink-0 text-xs text-muted">§{num}</span>
        <h2 className="serif flex-1 m-0 text-4xl font-normal tracking-tight leading-tight">
          {section.heading}
        </h2>
      </div>
      <div className="serif max-w-2xl text-base font-light leading-relaxed text-fg">
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
