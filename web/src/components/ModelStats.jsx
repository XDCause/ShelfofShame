import { exportUrl } from '../api.js'
import { BarList, ColumnChart } from './charts.jsx'
import { stepRows, yearRows } from './modelStatsRows.js'

// Under the Models page's numbers: kits finished per year ("painted this year"), time per build step, and the CSV downloads.
export default function ModelStats({ summary }) {
  const years = yearRows(summary.finished_by_year)
  const steps = stepRows(summary.stage_minutes)
  const thisYear = String(new Date().getFullYear())
  const done = years.find((y) => y.label === thisYear)?.value ?? 0
  return (
    <details className="card mst-box">
      <summary>Finished and time spent <span className="muted small">· {done} finished this year</span></summary>
      {years.length > 0 ? <ColumnChart title="Kits finished per year" rows={years} valueLabel="kits" labelValues /> : (
        <p className="muted small">No finished kits with a finished date yet.</p>
      )}
      {steps.length > 0 && (
        <>
          <h4 className="section-title">Time per build step</h4>
          <p className="muted small">Each timed session counts towards the step the kit was working on (the one after its last done).</p>
          <BarList title="Time per build step" rows={steps} valueLabel="minutes" />
        </>
      )}
      <p className="small mst-downloads">Download as CSV:{' '}
        <a href={exportUrl('models')} download>kits</a> · <a href={exportUrl('model-paints')} download>paints</a> ·{' '}
        <a href={exportUrl('builds')} download>build sessions</a> · <a href={exportUrl('paint-recipes')} download>recipes</a></p>
    </details>
  )
}
