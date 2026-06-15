import { Link, useParams } from '@tanstack/react-router'

import { ReportView } from '../components/ReportView'
import { useJobLineage } from '../hooks/useJobLineage'
import { useReport } from '../hooks/useReport'
import { ApiError } from '../services/api'

export default function ReportPage() {
  const { jobId } = useParams({ from: '/research/$jobId/report' })
  const { data, isLoading, error } = useReport(jobId)
  const { data: lineage } = useJobLineage(jobId)

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        style={{ background: 'var(--bg)', color: 'var(--muted)' }}
      >
        <span className="serif" style={{ fontSize: 18 }}>
          Loading report…
        </span>
      </div>
    )
  }

  if (error || !data) {
    const isNotReady = error instanceof ApiError && error.status === 404
    return (
      <div
        className="flex flex-col items-center justify-center min-h-screen gap-4"
        style={{ background: 'var(--bg)', color: 'var(--fg)' }}
      >
        <span className="serif" style={{ fontSize: 18 }}>
          {isNotReady
            ? 'Report is being prepared — check back shortly.'
            : 'Could not load the report.'}
        </span>
        <Link
          to="/research/$jobId"
          params={{ jobId }}
          className="micro"
          style={{ color: 'var(--scribe)' }}
        >
          ← Back to progress view
        </Link>
      </div>
    )
  }

  return <ReportView data={data} jobId={jobId} lineage={lineage} />
}
