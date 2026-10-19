import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Bits shared by Precision shooting's pages and panels: the choice lists, number formats, the summary,
// and the licence / club card (written for Queensland - but the numbers are yours to set).

let listsCache = null
export function useShootingLists() {
  const [lists, setLists] = useState(listsCache)
  useEffect(() => {
    if (!listsCache) api.shootingLists().then((l) => { listsCache = l; setLists(l) }).catch(() => {})
  }, [])
  return lists
}

export function useShootingSummary() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.shootingSummary().then(setData).catch((e) => setError(e.message)) }, [refreshKey])
  return { data, error }
}

// Rifles, ammo and ranges for the pickers (refreshed with the app). loaded: false until the first answer, so a
// form can wait for its choices instead of being rebuilt under you when they arrive.
export function useShootingThings() {
  const { refreshKey } = useApp()
  const [things, setThings] = useState({ rifles: [], ammo: [], ranges: [], loaded: false })
  useEffect(() => {
    Promise.all([api.rifles(), api.ammoList(), api.shootingRanges()])
      .then(([rifles, ammo, ranges]) => setThings({ rifles, ammo, ranges, loaded: true }))
      .catch(() => setThings((t) => ({ ...t, loaded: true })))
  }, [refreshKey])
  return things
}

export const angle = (v, unit) => (v == null ? '—' : `${Number(v).toFixed(2)} ${unit}`)
export const dist = (g) => `${g.distance} ${g.unit}`
export const plural = (n, one, many = `${one}s`) => `${(n ?? 0).toLocaleString()} ${n === 1 ? one : many}`
export const KIND_TONE = { Practice: 'teal', Match: 'purple', Zeroing: 'low', 'Ammo test': 'tint', 'Load development': 'tint', Fun: 'ok' }

// "325 328 326" or "325, 328" -> [325, 328, 326]
export const parseVelocities = (text) => (text ?? '').split(/[\s,;]+/).map(Number).filter((v) => v > 0 && v < 3000)

// A group from shot positions [{x_mm, y_mm}] (right / up of the aim): size (the two furthest apart), centre,
// mean radius - the same sums as the API's shotmath.group_stats, for the live board.
export function groupStats(points) {
  if (!points.length) return null
  const cx = points.reduce((a, p) => a + p.x_mm, 0) / points.length
  const cy = points.reduce((a, p) => a + p.y_mm, 0) / points.length
  let size = 0
  points.forEach((a, i) => points.slice(i + 1).forEach((b) => { size = Math.max(size, Math.hypot(a.x_mm - b.x_mm, a.y_mm - b.y_mm)) }))
  const mr = points.reduce((a, p) => a + Math.hypot(p.x_mm - cx, p.y_mm - cy), 0) / points.length
  return { size_mm: size, right_mm: cx, up_mm: cy, mean_radius_mm: mr }
}

// mm at a distance (metres) as the scope's unit
export const toAngle = (mm, metres, unit) => (unit === 'MIL' ? mm / metres : mm / (0.290888 * metres))

// "Dial 0.30 MIL down (3 clicks) and 0.10 MIL right (1 clicks)" - to bring a centre (mm) back to the aim point.
export function correction(upMm, rightMm, metres, unit, click) {
  const c = click || (unit === 'MIL' ? 0.1 : 0.25)
  const up = toAngle(upMm, metres, unit)
  const right = toAngle(rightMm, metres, unit)
  const clicks = (v) => { const n = Math.round(Math.abs(v) / c); return `${n} click${n === 1 ? '' : 's'}` }
  const moves = [Math.abs(up) >= c / 2 && `${Math.abs(up).toFixed(2)} ${unit} ${up > 0 ? 'down' : 'up'} (${clicks(up)})`,
    Math.abs(right) >= c / 2 && `${Math.abs(right).toFixed(2)} ${unit} ${right > 0 ? 'left' : 'right'} (${clicks(right)})`]
  return moves.some(Boolean) ? `Dial ${moves.filter(Boolean).join(' and ')}` : 'On the aim point'
}

// Live MOA / MIL for a size at a distance, in the form while you type.
export function sizeAngles(sizeMm, distance, unit) {
  const m = unit === 'yd' ? distance * 0.9144 : distance
  if (!(sizeMm > 0) || !(m > 0)) return null
  return { moa: sizeMm / (0.290888 * m), mil: sizeMm / m }
}

// Licence expiry, the club shoots you need this year, the cleaning interval - and your ranges.
export function LicenceCard({ summary }) {
  const { changed, showToast, openPanel } = useApp()
  const s = summary.settings
  const [form, setForm] = useState({ licence_expires: s.licence_expires ?? '', licence_note: s.licence_note ?? '',
    club_shoots_needed: s.club_shoots_needed ?? '', clean_every: s.clean_every ?? 200 })
  const [editing, setEditing] = useState(!s.licence_expires && s.club_shoots_needed == null)
  const [ranges, setRanges] = useState([])
  useEffect(() => { api.shootingRanges().then(setRanges).catch(() => {}) }, [summary])
  const save = async (e) => {
    e.preventDefault()
    try {
      await api.saveShootingSettings({ licence_expires: form.licence_expires || null, licence_note: form.licence_note || null,
        club_shoots_needed: form.club_shoots_needed === '' ? null : Number(form.club_shoots_needed), clean_every: Number(form.clean_every) || 200 })
      setEditing(false)
      changed()
      showToast('Saved')
    } catch (err) {
      showToast(err.message)
    }
  }
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const days = s.licence_days
  const needed = summary.club_needed
  const done = summary.this_year.club_days
  return (
    <section className="card home-card shoot-licence">
      <div className="section-head">
        <h2 className="home-card-title">Licence and club</h2>
        {!editing && <button type="button" className="plain small" onClick={() => setEditing(true)}>Edit</button>}
      </div>
      {editing ? (
        <form onSubmit={save} className="shoot-settings">
          <label className="field">Licence expires<input type="date" value={form.licence_expires} onChange={set('licence_expires')} /></label>
          <label className="field">Licence covers<input value={form.licence_note} onChange={set('licence_note')} placeholder="e.g. Category A, B" /></label>
          <label className="field">Club shoots needed a year
            <input type="number" min="0" max="365" value={form.club_shoots_needed} onChange={set('club_shoots_needed')} /></label>
          <label className="field">Clean every (rounds)<input type="number" min="1" value={form.clean_every} onChange={set('clean_every')} /></label>
          <p className="muted small">Queensland: a club membership as your genuine reason means taking part in enough club shoots each
            year. Set the number your club (and QPS Weapons Licensing) say applies to you.</p>
          <div className="button-row"><button type="submit" className="primary small">Save</button>
            <button type="button" className="plain small" onClick={() => setEditing(false)}>Cancel</button></div>
        </form>
      ) : (
        <dl className="shoot-facts">
          <dt>Licence</dt>
          <dd>{s.licence_expires ? <>{shortDate(s.licence_expires)}{' '}
            <span className={`pill ${days < 0 ? 'out' : days <= 90 ? 'low' : 'ok'}`}>{days < 0 ? 'Expired' : `${days} days`}</span></>
            : <span className="muted">expiry not set</span>}{s.licence_note && <span className="muted"> · {s.licence_note}</span>}</dd>
          <dt>Club shoots {summary.year}</dt>
          <dd>{done}{needed != null && <> of {needed} <span className={`pill ${done >= needed ? 'ok' : 'low'}`}>
            {done >= needed ? 'Done for the year' : `${needed - done} to go`}</span></>}</dd>
        </dl>
      )}
      <h3 className="shoot-subhead">Ranges</h3>
      <ul className="list plain-list">
        {ranges.map((r) => (
          <li key={r.range_id}>
            <button type="button" className="row-button" onClick={() => openPanel('shootrange', { id: r.range_id, range: r })}>
              <span className="grow">
                <span className="item-title">{r.name}</span>
                <span className="item-meta">{[r.kind, r.distances, r.counts_for_club ? 'counts as a club shoot' : null,
                  r.sessions ? plural(r.sessions, 'session') : null].filter(Boolean).join(' · ')}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className="plain small" onClick={() => openPanel('shootrange', {})}>+ Add a range</button>
    </section>
  )
}
