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
  // (rounded: 3 x 0.2 is 0.6000000000000001 in floating point)
  return { top, steps: Array.from({ length: Math.round(top / step) + 1 }, (_, i) => Number((i * step).toPrecision(12))) }
}
const compact = (n) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K` : String(n))

export function ChartTable({ title, rows, valueLabel }) {
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
              <div key={r.label} className="chart-slot" tabIndex={0} role="img" aria-label={`${r.label}: ${r.value.toLocaleString()} ${valueLabel}`}
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

// A line over time (one series, e.g. a rating): rows [{x: 'YYYY-MM-DD', y, tip?}], oldest first.
// The axis is fitted to the values (a rating doesn't start at 0); hovering shows the nearest
// point with a crosshair; dots only when there are few points.
export function LineChart({ title, rows, valueLabel, height = 200 }) {
  const [hover, setHover] = useState(null)
  if (rows.length < 2) return <p className="muted small">Not enough games yet to draw this.</p>
  const ys = rows.map((r) => r.y)
  const span = Math.max(...ys) - Math.min(...ys) || 50
  const step = [10, 20, 25, 50, 100, 200, 250, 500].find((s) => span / s <= 5) ?? 1000
  const lo = Math.floor((Math.min(...ys) - span * 0.05) / step) * step
  const hi = Math.ceil((Math.max(...ys) + span * 0.05) / step) * step
  const steps = Array.from({ length: Math.round((hi - lo) / step) + 1 }, (_, i) => lo + i * step)
  const t = rows.map((r) => new Date(`${r.x}T12:00:00`).getTime())
  const t0 = t[0], t1 = t[t.length - 1] || t0 + 1
  const X = (i) => (100 * (t[i] - t0)) / (t1 - t0 || 1)
  const Y = (v) => 100 - (100 * (v - lo)) / (hi - lo || 1)
  const points = rows.map((r, i) => `${X(i)},${Y(r.y)}`).join(' ')
  const nearest = (clientX, box) => {
    const at = t0 + ((clientX - box.left) / box.width) * (t1 - t0)
    let best = 0
    t.forEach((v, i) => { if (Math.abs(v - at) < Math.abs(t[best] - at)) best = i })
    return best
  }
  const day = (x, opts) => new Date(`${x}T12:00:00`).toLocaleDateString('en-AU', opts)
  const h = hover != null ? rows[hover] : null
  return (
    <figure className="chart line-chart" aria-label={`${title}: from ${rows[0].y} to ${rows[rows.length - 1].y}`}>
      <div className="chart-plot" style={{ height }}>
        <div className="chart-grid" aria-hidden="true">
          {steps.map((s) => <span key={s} className="chart-gridline" style={{ bottom: `${100 - Y(s)}%` }}><span>{s}</span></span>)}
        </div>
        <svg className="line-svg" viewBox="0 0 100 100" preserveAspectRatio="none" role="presentation"
          onMouseMove={(e) => setHover(nearest(e.clientX, e.currentTarget.getBoundingClientRect()))}
          onMouseLeave={() => setHover(null)}>
          <polyline points={points} className="line-path" vectorEffect="non-scaling-stroke" />
          {hover != null && <line x1={X(hover)} x2={X(hover)} y1="0" y2="100" className="line-cross" vectorEffect="non-scaling-stroke" />}
        </svg>
        {rows.length <= 40 && rows.map((r, i) => (
          <span key={r.x} className="line-dot" style={{ left: `${X(i)}%`, top: `${Y(r.y)}%` }} aria-hidden="true" />
        ))}
        {h && (
          <>
            <span className="line-dot on" style={{ left: `${X(hover)}%`, top: `${Y(h.y)}%` }} aria-hidden="true" />
            <span className="chart-tip line-tip" role="tooltip" style={{ left: `${Math.min(85, Math.max(15, X(hover)))}%` }}>
              <strong>{h.y.toLocaleString()}</strong> {valueLabel}<br /><span>{h.tip ?? day(h.x, { day: 'numeric', month: 'short', year: 'numeric' })}</span>
            </span>
          </>
        )}
      </div>
      <div className="line-labels" aria-hidden="true">
        <span>{day(rows[0].x, { month: 'short', year: 'numeric' })}</span>
        <span>{day(rows[rows.length - 1].x, { month: 'short', year: 'numeric' })}</span>
      </div>
      <ChartTable title="Day" valueLabel={valueLabel}
        rows={[...rows].reverse().map((r) => ({ label: day(r.x, { day: 'numeric', month: 'short', year: 'numeric' }), value: r.y }))} />
    </figure>
  )
}
