import { useState } from 'react'
import { api, shortDate } from '../../api.js'
import { LineChart } from '../../components/charts.jsx'
import { GolfIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import { PLAYS_LIKE, hcpText, nineLabel, num, oneADay, sgRows, statText, toPar, weakest } from './golfFormat.js'

// Golf's shared pieces for its pages and panels (not Home: loaded with the pages): a round's row, a grid of
// numbers, "plays like a ...", strokes gained, the handicap's line and the settings card.

// Axis steps for small numbers (a handicap, a score): the charts' LineChart starts at 10 otherwise.
export const GOLF_STEPS = [0.5, 1, 2, 5, 10, 20, 50]

// A round in a list: date, course, tees; the score (gross and to par, or points), little FIR / GIR / putts.
export function RoundRow({ r, showCounted = false }) {
  const { openPanel } = useApp()
  const score = r.gross != null ? `${r.gross} (${toPar(r.to_par)})` : r.entered < r.of ? `${r.entered} of ${r.of} holes` : 'picked up'
  const bits = [r.fairway_chances ? `FIR ${r.fairways}/${r.fairway_chances}` : null, r.gir != null && r.entered ? `GIR ${r.gir}` : null,
    r.putts != null ? `${r.putts} putts` : null]
  return (
    <li>
      <button type="button" className="row-button golf-round-row" onClick={() => openPanel('golfround', { id: r.round_id })}>
        <span className="stat-icon ok" aria-hidden="true"><GolfIcon size={18} /></span>
        <span className="grow">
          <span className="item-title">{r.course_name}</span>
          <span className="item-meta">
            <span>{shortDate(r.played_on)}</span>
            {r.tee_name && <span className="golf-tee"><i className="golf-teedot" style={{ background: r.tee_colour ?? 'var(--faint)' }} />{r.tee_name}</span>}
            {nineLabel(r.holes) && <span>{nineLabel(r.holes)}</span>}
            {r.competition && <span>{r.competition}</span>}
            {bits.filter(Boolean).length > 0 && <span>{bits.filter(Boolean).join(' · ')}</span>}
          </span>
        </span>
        <span className="golf-round-score">
          <strong>{r.format === 'Stableford' && r.entered ? `${r.points} pts` : score}</strong>
          <span className="muted small">{r.format === 'Stableford' && r.entered ? score : r.format}</span>
        </span>
        {r.status === 'playing' && <span className="pill low">Playing</span>}
        {showCounted && r.counted && <span className="pill ok" title="One of the best 8 of your last 20: it counts for your handicap">Counts</span>}
      </button>
    </li>
  )
}

// A row of labelled numbers: [{label, value, sub?}] (nulls left out).
export function Numbers({ items }) {
  return (
    <dl className="golf-numbers">
      {items.filter(Boolean).map((x) => (
        <div key={x.label}><dt>{x.label}</dt><dd>{x.value}{x.sub && <span className="muted small"> {x.sub}</span>}</dd></div>
      ))}
    </dl>
  )
}

// "Plays like a ...": each stat, the handicap it looks like, your target's average - and the weakest marked.
export function PlaysLike({ stats, bench, target }) {
  const like = stats?.plays_like ?? {}
  const shown = PLAYS_LIKE.filter((p) => stats?.[p.key] != null)
  if (!shown.length) return <p className="muted small">Fill in fairways, putts and penalties on your cards and this shows which part of your game is furthest behind.</p>
  const worst = weakest(like)
  return (
    <>
      <div className="golf-table-wrap" tabIndex={0} role="region" aria-label="Plays like (scrolls sideways)">
        <table className="golf-table">
          <thead><tr><th scope="col">Stat</th><th scope="col">You</th><th scope="col">Plays like</th>
            {bench && <th scope="col">At {hcpText(target)}</th>}</tr></thead>
          <tbody>
            {shown.map((p) => (
              <tr key={p.key} className={p.key === worst ? 'golf-worst' : undefined}>
                <th scope="row">{p.label}{p.key === worst && <span className="pill low golf-work-on">Work on this</span>}</th>
                <td>{statText(p.key, stats[p.key])}</td>
                <td>{like[p.key] != null ? hcpText(like[p.key]) : '—'}</td>
                {bench && <td>{statText(p.key, bench[p.key])}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">"Plays like": the handicap whose players average your number. Rough averages from published amateur
        stats - a guide to where your strokes go, not gospel.{bench ? ` The last column: a ${hcpText(target)} handicapper's average (your target).` : ''}</p>
    </>
  )
}

// Strokes gained per 18 holes by category (only categories with holes), the lowest marked.
export function StrokesGained({ sg }) {
  const rows = sgRows(sg)
  if (!rows.length) return <p className="muted small">Mark your shots on the course (Play on the phone) and type the first putt's length:
    strokes gained shows where you lose the most.</p>
  const most = Math.max(1, ...rows.map((r) => Math.abs(r.value)))
  const low = rows.reduce((a, b) => (b.value < a.value ? b : a))
  return (
    <>
      <ul className="golf-sg">
        {rows.map((r) => (
          <li key={r.key} className={r.key === low.key && rows.length > 1 ? 'golf-worst' : undefined}>
            <span className="golf-sg-name">{r.label}<span className="muted small"> {r.holes} holes</span></span>
            <span className="golf-sg-track" aria-hidden="true">
              <span className={`golf-sg-bar ${r.value < 0 ? 'minus' : 'plus'}`}
                style={{ width: `${(50 * Math.abs(r.value)) / most}%`, [r.value < 0 ? 'right' : 'left']: '50%' }} />
            </span>
            <span className="golf-sg-value">{r.value > 0 ? '+' : r.value < 0 ? '−' : ''}{num(Math.abs(r.value), 2)}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">Per 18 holes, against a tour pro: everyone's below zero - what matters is which is lowest.</p>
    </>
  )
}

// The handicap's history as a line (one point a day).
export function HandicapLine({ history, height = 160 }) {
  const rows = oneADay((history ?? []).map((h) => ({ x: h.day, y: Number(h.index), tip: shortDate(h.day) })))
  return <LineChart title="Handicap" rows={rows} valueLabel="handicap" height={height} stepChoices={GOLF_STEPS}
    empty="Your handicap's line starts after your third counting round." />
}

// "+1.2" (a plus handicap) or "18.4" -> the number the API keeps (plus = below 0); '' -> null; NaN if not a number.
const readHcp = (text) => {
  const t = String(text).trim()
  if (t === '') return null
  return t.startsWith('+') ? -Number(t.slice(1)) : Number(t)
}
const showHcp = (v) => (v == null ? '' : Number(v) < 0 ? `+${Math.abs(Number(v))}` : String(Number(v)))

// Your official GA Handicap (typed from GolfLink), the target, the allowance, the home course.
export function GolfSettingsCard({ settings, courses, onSaved }) {
  const { changed, showToast } = useApp()
  const [form, setForm] = useState(() => ({
    official_handicap: showHcp(settings.official_handicap), official_as_of: settings.official_as_of ?? '',
    target_handicap: showHcp(settings.target_handicap), allowance: String(Number(settings.allowance ?? 0.93)),
    home_course_id: settings.home_course_id != null ? String(settings.home_course_id) : '',
  }))
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const save = async (e) => {
    e.preventDefault()
    setError('')
    const official = readHcp(form.official_handicap)
    const target = readHcp(form.target_handicap)
    if (Number.isNaN(official) || Number.isNaN(target)) { setError('A handicap is a number, like 18.4 (or +1.2).'); return }
    try {
      await api.saveGolfSettings({ official_handicap: official, official_as_of: form.official_as_of || null, target_handicap: target,
        allowance: Number(form.allowance) || 0.93, home_course_id: form.home_course_id ? Number(form.home_course_id) : null })
      changed()
      showToast('Saved')
      onSaved?.()
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="golf-settings" onSubmit={save}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="golf-form-grid">
        <label className="field">Official GA Handicap
          <input inputMode="decimal" value={form.official_handicap} onChange={set('official_handicap')} placeholder="e.g. 18.4" /></label>
        <label className="field">As of<input type="date" value={form.official_as_of} onChange={set('official_as_of')} /></label>
        <label className="field">Your target<input inputMode="decimal" value={form.target_handicap} onChange={set('target_handicap')} placeholder="e.g. 12" /></label>
        <label className="field">Daily handicap allowance
          <select value={form.allowance} onChange={set('allowance')}>
            <option value="0.93">93% (Golf Australia)</option>
            <option value="0.95">95% (four-ball)</option>
            <option value="1">100% (plain WHS)</option>
            {!['0.93', '0.95', '1'].includes(form.allowance) && <option value={form.allowance}>{Math.round(Number(form.allowance) * 100)}%</option>}
          </select></label>
        <label className="field">Home course
          <select value={form.home_course_id} onChange={set('home_course_id')}>
            <option value="">—</option>
            {(courses ?? []).map((c) => <option key={c.course_id} value={c.course_id}>{c.name}</option>)}
          </select></label>
      </div>
      <p className="muted small">The app's handicap is an estimate: the World Handicap System's sums on your finished rounds (best 8 of
        the last 20), without the playing-conditions adjustment or the caps. GolfLink's number is the official one - type it here and
        it's used instead (leave it blank to use the estimate). A plus handicap: type it with a + (e.g. +1.2).</p>
      <div className="button-row"><button type="submit" className="primary small">Save</button></div>
    </form>
  )
}
