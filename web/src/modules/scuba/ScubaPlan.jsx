import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { CAVEAT, bestMix, ead, mod, ppO2, sac } from './diveCalc.js'

// The planner page: the no-decompression table for your gas, "plan a dive" (the API's Buhlmann ZHL-16C with gradient
// factors: stops, gas, turn pressure, rock bottom) and the nitrox calculators (diveCalc.js, done in the browser).
// Everything here is for learning and checking - the dive computer and the training rule come first.

export function Caveat() {
  return <p className="alert low scuba-caveat" role="note"><strong>{CAVEAT}</strong> Tables and plans are only as good as their assumptions.</p>
}

const num = (v) => (v === '' || v == null ? null : Number(v))
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

// ---- the no-decompression table
function NdlTable({ gasO2, gfHigh }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    api.scubaNdl({ gas_o2: gasO2, gf_high: gfHigh }).then((r) => { if (live) { setRows(r); setError('') } })
      .catch((e) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [gasO2, gfHigh])
  if (error) return <p className="alert error" role="alert">{error}</p>
  if (!rows) return <p className="muted loading">Working it out...</p>
  return (
    <div className="scuba-table-wrap">
      <table className="scuba-table">
        <caption className="scuba-vh">No-decompression limits by depth</caption>
        <thead><tr><th scope="col">Depth</th><th scope="col">No-stop time</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.depth}>
              <th scope="row">{r.depth} m</th>
              <td>{r.ndl == null ? <span className="muted">beyond this gas&apos;s MOD</span> : `${r.ndl} min`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---- plan a dive
function PlanResult({ plan }) {
  const fmt = (v, unit, d = 0) => (v == null ? '—' : `${Number(v).toFixed(d)}${unit}`)
  return (
    <div className="scuba-result">
      {plan.warnings?.length > 0 && (
        <ul className="scuba-warnings">{plan.warnings.map((w) => <li key={w} className="alert low small">{w}</li>)}</ul>
      )}
      <dl className="scuba-numbers">
        <div><dt>No-stop time left</dt><dd>{plan.ndl == null ? '—' : `${plan.ndl} min`}</dd></div>
        <div><dt>Time to surface</dt><dd>{fmt(plan.tts, ' min')}</dd></div>
        <div><dt>Runtime</dt><dd>{fmt(plan.runtime, ' min')}</dd></div>
        <div><dt>ppO2 at depth</dt><dd>{fmt(plan.ppo2, ' bar', 2)}</dd></div>
        <div><dt>MOD</dt><dd>{fmt(plan.mod, ' m', 1)}</dd></div>
        <div><dt>CNS / OTU</dt><dd>{fmt(plan.cns, '%')} / {fmt(plan.otu, '')}</dd></div>
        <div><dt>Gas for the plan</dt><dd>{fmt(plan.gas_l, ' L')} <span className="muted small">({fmt(plan.gas_bar, ' bar')})</span></dd></div>
        <div><dt>Ends with</dt><dd>{fmt(plan.end_bar, ' bar')}</dd></div>
        <div><dt>Turn at</dt><dd>{fmt(plan.turn_bar, ' bar')}</dd></div>
        <div><dt>Rock bottom</dt><dd>{fmt(plan.rock_bottom_bar, ' bar')}</dd></div>
      </dl>
      <h3 className="scuba-h3">Stops</h3>
      {plan.stops?.length ? (
        <ul className="scuba-stops">
          {plan.stops.map((s) => <li key={s.depth}><strong>{s.depth} m</strong> for {s.minutes} min</li>)}
        </ul>
      ) : <p className="muted">No decompression stops: a direct ascent is within the plan (a 3 minute safety stop at 5 m is still good practice).</p>}
    </div>
  )
}

function PlanForm({ settings }) {
  const [f, setF] = useState({ depth: '18', minutes: '40', gas_o2: String(settings?.gas_o2 ?? 21), gf_low: String(settings?.gf_low ?? 40),
    gf_high: String(settings?.gf_high ?? 85), sac: String(settings?.sac_l_min ?? 20), tank_l: String(settings?.tank_l ?? 12), start_bar: '200', repetitive: false })
  const [plan, setPlan] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const run = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const body = { depth: num(f.depth), minutes: num(f.minutes), gas_o2: num(f.gas_o2), gf_low: num(f.gf_low), gf_high: num(f.gf_high),
        sac: num(f.sac), tank_l: num(f.tank_l), start_bar: num(f.start_bar), repetitive: f.repetitive }
      setPlan(await api.scubaPlan(body))
    } catch (err) {
      setError(err.message)
      setPlan(null)
    }
    setBusy(false)
  }
  return (
    <form className="scuba-form" onSubmit={run}>
      <label className="field">Depth (m)<input type="number" inputMode="decimal" min="3" max="60" step="0.5" value={f.depth} onChange={set('depth')} required /></label>
      <label className="field">Bottom time (min)<input type="number" inputMode="numeric" min="1" max="300" value={f.minutes} onChange={set('minutes')} required /></label>
      <label className="field">Oxygen (%)<input type="number" inputMode="numeric" min="21" max="100" value={f.gas_o2} onChange={set('gas_o2')} required /></label>
      <label className="field">Gradient factor low<input type="number" inputMode="numeric" min="10" max="100" value={f.gf_low} onChange={set('gf_low')} /></label>
      <label className="field">Gradient factor high<input type="number" inputMode="numeric" min="10" max="100" value={f.gf_high} onChange={set('gf_high')} /></label>
      <label className="field">Your SAC (L/min)<input type="number" inputMode="decimal" min="5" max="60" step="0.5" value={f.sac} onChange={set('sac')} /></label>
      <label className="field">Tank (L)<input type="number" inputMode="decimal" min="1" max="30" step="0.5" value={f.tank_l} onChange={set('tank_l')} /></label>
      <label className="field">Start pressure (bar)<input type="number" inputMode="numeric" min="50" max="300" value={f.start_bar} onChange={set('start_bar')} /></label>
      <label className="scuba-check"><input type="checkbox" checked={f.repetitive} onChange={set('repetitive')} /> A repeat dive (start from the tissues your last 24 h of logged dives left)</label>
      <div className="scuba-form-actions">
        <button type="submit" className="primary" disabled={busy}>{busy ? 'Working it out...' : 'Plan it'}</button>
      </div>
      {error && <p className="alert error" role="alert">{error}</p>}
      {plan && <PlanResult plan={plan} />}
    </form>
  )
}

// ---- the calculators
function Calculators({ settings }) {
  const [o2, setO2] = useState(String(settings?.gas_o2 ?? 32))
  const [depth, setDepth] = useState('30')
  const [limit, setLimit] = useState('1.4')
  const [want, setWant] = useState('1.4')
  const [wantDepth, setWantDepth] = useState('30')
  const [s, setS] = useState({ startBar: '200', endBar: '60', tankL: String(settings?.tank_l ?? 12), minutes: '45', avgDepth: '14' })
  const o = clamp(num(o2) ?? 21, 21, 100)
  const d = Math.max(0, num(depth) ?? 0)
  const lim = num(limit) ?? 1.4
  const setSac = (k) => (e) => setS({ ...s, [k]: e.target.value })
  const mix = bestMix(Math.max(0, num(wantDepth) ?? 0), num(want) ?? 1.4)
  const rate = sac(s)
  return (
    <div className="scuba-calcs">
      <div className="scuba-calc">
        <h3 className="scuba-h3">Your gas</h3>
        <div className="scuba-calc-fields">
          <label className="field">Oxygen (%)<input type="number" inputMode="numeric" min="21" max="100" value={o2} onChange={(e) => setO2(e.target.value)} /></label>
          <label className="field">Depth (m)<input type="number" inputMode="decimal" min="0" max="100" value={depth} onChange={(e) => setDepth(e.target.value)} /></label>
          <label className="field">ppO2 limit
            <select value={limit} onChange={(e) => setLimit(e.target.value)}><option value="1.4">1.4 (working)</option><option value="1.6">1.6 (contingency)</option></select></label>
        </div>
        <dl className="scuba-numbers">
          <div><dt>MOD at {lim}</dt><dd>{mod(o, lim)} m</dd></div>
          <div><dt>MOD at 1.4 / 1.6</dt><dd>{mod(o, 1.4)} / {mod(o, 1.6)} m</dd></div>
          <div><dt>ppO2 at {d} m</dt><dd className={ppO2(o, d) > lim ? 'scuba-over' : ''}>{ppO2(o, d).toFixed(2)} bar{ppO2(o, d) > lim ? ' (over the limit)' : ''}</dd></div>
          <div><dt>Equivalent air depth at {d} m</dt><dd>{ead(o, d)} m</dd></div>
        </dl>
      </div>
      <div className="scuba-calc">
        <h3 className="scuba-h3">Best mix</h3>
        <div className="scuba-calc-fields">
          <label className="field">Planned depth (m)<input type="number" inputMode="decimal" min="0" max="100" value={wantDepth} onChange={(e) => setWantDepth(e.target.value)} /></label>
          <label className="field">ppO2 limit
            <select value={want} onChange={(e) => setWant(e.target.value)}><option value="1.4">1.4 (working)</option><option value="1.6">1.6 (contingency)</option></select></label>
        </div>
        <p className="scuba-big">{mix < 21 ? 'Air is already over the limit here' : `${mix}% oxygen`}</p>
        <p className="muted small">The richest whole-percent mix that keeps ppO2 under the limit at that depth.</p>
      </div>
      <div className="scuba-calc">
        <h3 className="scuba-h3">Your SAC from a dive</h3>
        <div className="scuba-calc-fields">
          <label className="field">Start (bar)<input type="number" inputMode="numeric" value={s.startBar} onChange={setSac('startBar')} /></label>
          <label className="field">End (bar)<input type="number" inputMode="numeric" value={s.endBar} onChange={setSac('endBar')} /></label>
          <label className="field">Tank (L)<input type="number" inputMode="decimal" value={s.tankL} onChange={setSac('tankL')} /></label>
          <label className="field">Time (min)<input type="number" inputMode="numeric" value={s.minutes} onChange={setSac('minutes')} /></label>
          <label className="field">Average depth (m)<input type="number" inputMode="decimal" value={s.avgDepth} onChange={setSac('avgDepth')} /></label>
        </div>
        <p className="scuba-big">{rate == null ? '—' : `${rate} L/min`}</p>
        <p className="muted small">Litres used a minute, scaled back to the surface. Rough guide for a relaxed dive: 12-20.</p>
      </div>
    </div>
  )
}

export function PlanView() {
  const [settings, setSettings] = useState(null)         // null while loading; {} when unavailable
  const [gas, setGas] = useState('')
  const [gf, setGf] = useState('')
  useEffect(() => {
    api.scubaToolSettings().then(setSettings).catch(() => setSettings({}))
  }, [])
  if (!settings) return <p className="muted loading">Loading...</p>
  const ndlGas = gas === '' ? settings.gas_o2 ?? 21 : clamp(num(gas) ?? 21, 21, 100)
  const ndlGf = gf === '' ? settings.gf_high ?? 85 : clamp(num(gf) ?? 85, 10, 100)
  return (
    <section className="page scuba-tools">
      <Caveat />
      <section className="card">
        <h2 className="home-card-title">No-stop limits</h2>
        <p className="muted small">How long you can stay at each depth and still come straight up (Buhlmann ZHL-16C, gradient factor high {ndlGf}).</p>
        <div className="scuba-calc-fields">
          <label className="field">Oxygen (%)<input type="number" inputMode="numeric" min="21" max="100" value={gas === '' ? ndlGas : gas} onChange={(e) => setGas(e.target.value)} /></label>
          <label className="field">Gradient factor high<input type="number" inputMode="numeric" min="10" max="100" value={gf === '' ? ndlGf : gf} onChange={(e) => setGf(e.target.value)} /></label>
        </div>
        <NdlTable gasO2={ndlGas} gfHigh={ndlGf} />
      </section>
      <section className="card">
        <h2 className="home-card-title">Plan a dive</h2>
        <PlanForm settings={settings} />
      </section>
      <section className="card">
        <h2 className="home-card-title">Nitrox calculators</h2>
        <Calculators settings={settings} />
      </section>
    </section>
  )
}
