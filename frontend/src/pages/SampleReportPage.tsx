import { ReportView } from '../components/ReportView'
import { SAMPLE_REPORT } from '../lib/sample-report'

export default function SampleReportPage() {
  return <ReportView data={SAMPLE_REPORT} jobId={SAMPLE_REPORT.job.id} sample />
}
