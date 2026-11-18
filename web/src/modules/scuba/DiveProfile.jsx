import { useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { clockOf } from './diveCalc.js'

// A dive's profile (the computer's samples, analysed by the API: GET /scuba/dives/{id}/analysis): depth downwards,
// time across, water temperature as a faint second line, ascents faster than 10 m/min shaded red, the 3-6 m safety
// stop band, and a strip underneath for the tissue loading (the leading compartment, % of its M-value). Hover, or
// tap and drag, reads off depth, time, temperature and loading. Drawn in SVG with the app's colour tokens.
const W = 480
const H = 220
const PAD = { l: 34, r: 8, t: 8, b: 18 }
const STRIP = { y: 244, h: 26 }
const TOTAL_H = 278

// the nearest sample (by time) to a time in seconds
const nearestIndex = (rows, s) => {
  let best = 0
  rows.forEach((r, i) => { if (Math.abs(r[0] - s) < Math.abs(rows[best][0] - s)) best = i })
  return best
}
const tissueAt = (tissues, s) => (tissues?.length ? tissues[nearestIndex(tissues, s)][1] : null)
const niceStep = (max) => [5, 10, 20, 50].find((st) => max / st <= 6) ?? 50

export function DiveProfile({ diveId, hasProfile }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [hover, setHover] = useState(null)       // a sample index
  const svgRef = useRef(null)
  useEffect(() => {
    if (!hasProfile) return undefined
    let live = true
    api.scubaAnalysis(diveId).then((d) => { if (live) { setData(d); setError('') } })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [diveId, hasProfile])
  if (!hasProfile) return null
  if (error) return <p className="muted small">{error}</p>
  if (!data) return <p className="muted loading">Loading the profile...</p>
  const rows = data.profile ?? []
  if (rows.length < 2) return <p className="muted small">This dive&apos;s profile has too few samples to draw.</p>

  const tEnd = rows[rows.length - 1][0] || 1
  const dMax = Math.max(...rows.map((r) => r[1]), 6)
  const step = niceStep(dMax)
  const dTop = Math.ceil((dMax * 1.05) / step) * step
  const X = (s) => PAD.l + ((W - PAD.l - PAD.r) * s) / tEnd
  const Y = (d) => PAD.t + ((H - PAD.t - PAD.b) * d) / dTop
  const line = rows.map((r) => `${X(r[0]).toFixed(1)},${Y(r[1]).toFixed(1)}`).join(' ')
  const area = `${X(rows[0][0])},${Y(0)} ${line} ${X(tEnd)},${Y(0)}`
  const temps = rows.filter((r) => r[2] != null)
  const tLo = temps.length ? Math.min(...temps.map((r) => r[2])) : 0
  const tHi = temps.length ? Math.max(...temps.map((r) => r[2])) : 1
  const TY = (c) => PAD.t + (H - PAD.t - PAD.b) * (0.85 - (0.7 * (c - tLo)) / (tHi - tLo || 1))
  const tempLine = temps.length > 1 ? temps.map((r) => `${X(r[0]).toFixed(1)},${TY(r[2]).toFixed(1)}`).join(' ') : ''
  const grid = Array.from({ length: Math.floor(dTop / step) + 1 }, (_, i) => i * step)
  const minutes = Math.max(1, Math.floor(tEnd / 60))
  const tickEvery = minutes > 90 ? 20 : minutes > 40 ? 10 : 5
  const ticks = Array.from({ length: Math.floor(minutes / tickEvery) + 1 }, (_, i) => i * tickEvery)

  const tissues = data.tissues ?? []
  const tMaxPct = Math.max(100, ...tissues.map((r) => r[1]))
  const stripY = (pct) => (STRIP.y + STRIP.h - (STRIP.h * Math.min(pct, tMaxPct)) / tMaxPct).toFixed(1)
  const stripPath = tissues.length > 1
    ? `${X(tissues[0][0])},${STRIP.y + STRIP.h} ${tissues.map((r) => `${X(r[0]).toFixed(1)},${stripY(r[1])}`).join(' ')} ${X(tissues[tissues.length - 1][0])},${STRIP.y + STRIP.h}`
    : ''

  const move = (e) => {
    const box = svgRef.current.getBoundingClientRect()
    const x = ((e.clientX - box.left) / (box.width || W)) * W
    const s = ((x - PAD.l) / (W - PAD.l - PAD.r)) * tEnd
    setHover(nearestIndex(rows, Math.min(tEnd, Math.max(0, s))))
  }
  const h = hover != null ? rows[hover] : null
  const load = h ? tissueAt(tissues, h[0]) : null
  const stop = data.safety_stop
  const warnings = data.ascent_warnings ?? []
  const fig = (v, unit, d = 1) => (v == null ? '—' : `${Number(v).toFixed(d)}${unit}`)

  return (
    <figure className="dive-profile" aria-label={`Dive profile: ${Math.round(dMax * 10) / 10} m deepest over ${minutes} minutes`}>
      <svg ref={svgRef} className="dive-profile-svg" viewBox={`0 0 ${W} ${TOTAL_H}`} role="img"
        aria-label="Depth against time" onPointerMove={move} onPointerDown={move} onPointerLeave={() => setHover(null)}>
        {grid.map((d) => (
          <g key={d}>
            <line className="dive-grid" x1={PAD.l} x2={W - PAD.r} y1={Y(d)} y2={Y(d)} />
            <text className="dive-axis" x={PAD.l - 4} y={Y(d) + 3} textAnchor="end">{d}</text>
          </g>
        ))}
        {ticks.filter((m) => X(m * 60) < W - PAD.r - 28).map((m) => <text key={m} className="dive-axis" x={X(m * 60)} y={H - 3} textAnchor="middle">{m}</text>)}
        <text className="dive-axis" x={W - PAD.r} y={H - 3} textAnchor="end">min</text>
        <rect className="dive-stopband" x={PAD.l} y={Y(3)} width={W - PAD.l - PAD.r} height={Y(6) - Y(3)} />
        <text className="dive-stoplabel" x={W - PAD.r - 3} y={Y(3) + 10} textAnchor="end">safety stop 3-6 m</text>
        {warnings.map((w) => (
          <rect key={`${w.from_s}-${w.to_s}`} className="dive-fast" x={X(w.from_s)} y={PAD.t}
            width={Math.max(3, X(w.to_s) - X(w.from_s))} height={H - PAD.t - PAD.b} />
        ))}
        <polygon className="dive-area" points={area} />
        {tempLine && <polyline className="dive-temp" points={tempLine} />}
        <polyline className="dive-depth" points={line} />
        <text className="dive-axis" x={PAD.l} y={STRIP.y - 3}>tissue loading (% of M-value)</text>
        <rect className="dive-strip-bg" x={PAD.l} y={STRIP.y} width={W - PAD.l - PAD.r} height={STRIP.h} />
        {stripPath && <polygon className="dive-strip" points={stripPath} />}
        {h && (
          <g aria-hidden="true">
            <line className="dive-cross" x1={X(h[0])} x2={X(h[0])} y1={PAD.t} y2={STRIP.y + STRIP.h} />
            <circle className="dive-dot" cx={X(h[0])} cy={Y(h[1])} r="4" />
          </g>
        )}
      </svg>
      <p className="dive-readout" role="status">
        {h ? (
          <>
            <strong>{clockOf(h[0])}</strong> · {h[1].toFixed(1)} m{h[2] != null && <> · {h[2].toFixed(1)} °C</>}
            {load != null && <> · tissues {Math.round(load)}%</>}
          </>
        ) : <span className="muted">Hover or touch the chart to read it.</span>}
      </p>
      <ul className="dive-flags">
        <li className={stop?.found ? 'dive-flag ok' : 'dive-flag low'}>
          {stop?.found ? `Safety stop found (${clockOf(stop.seconds)} at 3-6 m)` : 'No safety stop found (3 min at 3-6 m)'}
        </li>
        {warnings.length > 0 ? (
          <li className="dive-flag out">
            {warnings.length} fast {warnings.length === 1 ? 'ascent' : 'ascents'} (over 10 m a minute), the worst {Math.max(...warnings.map((w) => w.rate)).toFixed(0)} m/min
          </li>
        ) : <li className="dive-flag ok">Ascent rate stayed within 10 m a minute</li>}
      </ul>
      <dl className="dive-figures">
        <div><dt>Surface GF</dt><dd>{fig(data.surface_gf, '%', 0)}</dd></div>
        <div><dt>CNS</dt><dd>{fig(data.cns, '%', 0)}</dd></div>
        <div><dt>OTU</dt><dd>{fig(data.otu, '', 0)}</dd></div>
        <div><dt>Max ppO2</dt><dd>{fig(data.max_ppo2, ' bar', 2)}</dd></div>
      </dl>
      <p className="muted small">Worked out from the samples by the app (Buhlmann ZHL-16C): for learning and checking - your dive computer and training rule.</p>
    </figure>
  )
}
