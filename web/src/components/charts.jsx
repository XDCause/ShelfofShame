import { useState } from 'react'

// Small charts in plain HTML/CSS (no chart library): one series each, in the app's accent colour,
// so a chart's title says what it shows and no legend is needed. Every column has a hover / focus
// tooltip, and every chart has "Show as a table" for the exact numbers.

// 0, 5, 10... - a round top for the axis, and its steps.
function niceScale(max, ticks = 4) {
  if (max <= 0) return { top: 1, steps: [0, 1] }
  const raw = max / ticks
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw)
  const top = Math.ceil(max / step) * step
  return { top, steps: Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step) }
}
const compact = (n) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K` : String(n))

function ChartTable({ title, rows, valueLabel }) {
  return (
    <details className="chart-table">
      <summary>Show as a table</summary>
      <table>
        <thead><tr><th scope="col">{title}</th><th scope="col">{valueLabel}</th></tr></thead>
        <tbody>{rows.map((r) => <tr key={r.label}><td>{r.label}</td><td>{r.text ?? r.value.toLocaleString()}</td></tr>)}</tbody>
      </table>
    </details>
  )
}

// Columns from one baseline. rows: [{label, value, tip?}]. `tickEvery` = label every Nth column
// (for long runs like 24 months); `labelValues` = the value on every cap (for a few columns),
// else only the highest column is labelled.
export function ColumnChart({ title, rows, valueLabel, tickEvery = 1, labelValues = false, height = 180 }) {
  const [hover, setHover] = useState(null)
  const max = Math.max(0, ...rows.map((r) => r.value))
  const { top, steps } = niceScale(max)
  const highest = rows.findIndex((r) => r.value === max && max > 0)
  return (
    <figure className="chart" aria-label={title}>
      <div className="chart-plot" style={{ height }}>
        <div className="chart-grid" aria-hidden="true">
          {steps.map((s) => (
            <span key={s} className="chart-gridline" style={{ bottom: `${(s / top) * 100}%` }}><span>{compact(s)}</span></span>
          ))}
        </div>
        <div className="chart-columns">
          {rows.map((r, i) => {
            const showValue = (labelValues || i === highest) && r.value > 0
            return (
              <div key={r.label} className="chart-slot" tabIndex={0} aria-label={`${r.label}: ${r.value.toLocaleString()} ${valueLabel}`}
                onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
                onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
                <span className="chart-column" style={{ height: `${(r.value / top) * 100}%` }}>
                  {showValue && <span className="chart-cap">{compact(r.value)}</span>}
                </span>
                {hover === i && (
                  <span className="chart-tip" role="tooltip">
                    <strong>{r.value.toLocaleString()}</strong> {valueLabel}<br />
                    <span>{r.tip ?? r.label}</span>
                  </span>
                )}
              </div>
            )
          })}
        </div>
      </div>
      <div className="chart-labels" aria-hidden="true">
        {rows.map((r, i) => <span key={r.label}>{i % tickEvery === 0 || i === rows.length - 1 ? r.label : ''}</span>)}
      </div>
      <ChartTable title={title} rows={rows} valueLabel={valueLabel} />
    </figure>
  )
}

// Horizontal bars, longest first: a name, the bar, the value at its tip. rows: [{label, value, text?}]
export function BarList({ title, rows, valueLabel, onPick }) {
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <figure className="chart" aria-label={title}>
      <ul className="bar-list">
        {rows.map((r) => (
          <li key={r.label}>
            <button type="button" className="bar-row" onClick={() => onPick?.(r)} disabled={!onPick}
              title={`${r.label}: ${r.text ?? r.value.toLocaleString()}`}>
              <span className="bar-name">{r.label}</span>
              <span className="bar-track">
                <span className="bar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
                <span className="bar-value">{r.text ?? r.value.toLocaleString()}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <ChartTable title={title} rows={rows} valueLabel={valueLabel} />
    </figure>
  )
}
