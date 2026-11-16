import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { airLabel, clicksFor, compareWithDope, gapText } from './ballisticsHelpers.js'

// The ballistic solver beside the DOPE card: what the maths (BC, muzzle speed, sight height, zero and the day's air)
// predicts at each distance, next to what you confirmed. Maths: api/app/ballistics.py.
const BLANK = { session_id: '', temp_c: '', pressure_hpa: '', humidity_pct: '', wind_kmh: '10', zero_temp_c: '', zero_pressure_hpa: '', zero_humidity_pct: '' }

export default function BallisticsCard({ rifleId, ammoId, dopeRows }) {
  const [form, setForm] = useState(BLANK)
  const [applied, setApplied] = useState(BLANK)
  const [sessions, setSessions] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const at = (dopeRows ?? []).map((r) => r.m).join(',')
  useEffect(() => {
    if (rifleId) api.shootingSessions({ rifle_id: rifleId }).then((rows) => setSessions(rows.filter((s) => s.temp_c != null || s.pressure_hpa != null))).catch(() => setSessions([]))
  }, [rifleId])
  useEffect(() => {
    if (!rifleId || !ammoId) return
    api.ballistics({ rifle_id: rifleId, ammo_id: ammoId, at, max_m: 300, ...applied })
      .then((r) => { setResult(r); setError('') })
      .catch((e) => { setResult(null); setError(e.message) })
  }, [rifleId, ammoId, at, applied])
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  if (!ammoId) return <section className="card ballistics-card"><h2 className="home-card-title">Predicted</h2><p className="muted small">Pick an ammo above to see what the maths predicts for it.</p></section>
  const rows = result ? compareWithDope(result.rows, dopeRows) : []
  const unit = result?.unit ?? 'MOA'
  const click = result?.rifle.click
  return (
    <section className="card ballistics-card">
      <h2 className="home-card-title">Predicted against your DOPE</h2>
      <form className="shoot-noprint ballistics-form" onSubmit={(e) => { e.preventDefault(); setApplied(form) }} aria-label="The day's air">
        <div className="shoot-form-grid">
          <label className="field">From a session
            <select value={form.session_id} onChange={(e) => setForm({ ...BLANK, session_id: e.target.value, wind_kmh: form.wind_kmh })}>
              <option value="">Typed below</option>
              {sessions.map((s) => <option key={s.session_id} value={s.session_id}>{s.shot_on} · {airLabel(s)}</option>)}
            </select></label>
          <label className="field">Temperature (°C)<input type="number" step="0.1" value={form.temp_c} onChange={set('temp_c')} /></label>
          <label className="field">Pressure (hPa, at the range)<input type="number" step="0.1" value={form.pressure_hpa} onChange={set('pressure_hpa')} /></label>
          <label className="field">Humidity (%)<input type="number" min="0" max="100" value={form.humidity_pct} onChange={set('humidity_pct')} /></label>
          <label className="field">Crosswind (km/h)<input type="number" min="0" step="0.5" value={form.wind_kmh} onChange={set('wind_kmh')} /></label>
        </div>
        <details>
          <summary className="small">Where was it zeroed? (blank = a standard day)</summary>
          <div className="shoot-form-grid">
            <label className="field">Zero temperature (°C)<input type="number" step="0.1" value={form.zero_temp_c} onChange={set('zero_temp_c')} /></label>
            <label className="field">Zero pressure (hPa)<input type="number" step="0.1" value={form.zero_pressure_hpa} onChange={set('zero_pressure_hpa')} /></label>
            <label className="field">Zero humidity (%)<input type="number" min="0" max="100" value={form.zero_humidity_pct} onChange={set('zero_humidity_pct')} /></label>
          </div>
        </details>
        <button type="submit" className="secondary small">Work it out</button>
      </form>
      {error && <p className="alert error small">{error}</p>}
      {result && (
        <>
          <p className="small muted ballistics-air">
            {result.ammo.name}: {result.ammo.bc} {result.ammo.bc_model}, {result.ammo.mv_ms} m/s, sight {result.rifle.sight_mm} mm, zero {result.rifle.zero_m} m.
            Air {result.air.temp_c}°C, {result.air.pressure_hpa} hPa, {result.air.humidity_pct}% humidity:
            {' '}{result.air.density} kg/m³, density altitude {result.air.density_altitude_m} m{result.air.standard ? ' (a standard day)' : ''}.
          </p>
          {result.notes.map((n) => <p key={n} className="small muted">{n}</p>)}
          <div className="ballistics-scroll">
            <table className="shoot-table ballistics-table">
              <thead><tr><th>Distance</th><th>Predicted</th><th>Clicks</th><th>Yours</th><th>Gap</th><th>Drop</th>
                <th>Wind {result.wind_kmh} km/h</th><th>Time</th><th>Speed</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.m}>
                  <td>{r.m} m</td><td>{r.elevation.toFixed(2)} {unit}</td><td>{clicksFor(r.elevation, click) ?? '—'}</td>
                  <td>{r.mine != null ? `${r.mine} ${unit}` : '—'}</td><td>{gapText(r.gap, unit) || '—'}</td>
                  <td>{r.drop_cm} cm</td><td>{r.wind.toFixed(2)} {unit} · {r.drift_cm} cm</td><td>{r.time_s} s</td><td>{Math.round(r.velocity_ms)} m/s</td>
                </tr>))}</tbody>
            </table>
          </div>
          <p className="small muted">A prediction is a starting point: your confirmed groups are the truth. Point-mass maths with the standard {result.ammo.bc_model} drag curve.</p>
        </>
      )}
    </section>
  )
}
