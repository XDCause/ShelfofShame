import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, shortDate, today } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { Numbers, StrokesGained } from './golfCards.jsx'
import { HOLE_SETS, hcpText, holeSetOf, num, sgRows, toPar } from './golfFormat.js'
import { useGolfCourses, useGolfLists } from './golfParts.jsx'

// Golf's round panels: a round's scorecard (typed in after, hole by hole, right in the grid), its details, totals,
// stats, strokes gained and weather; and starting a new round (play it on the phone, or type in a card).

const holeChoices = (courseHoles) => (courseHoles === 9 ? [['front', '9 holes']] : Object.entries(HOLE_SETS))

// ---------------------------------------------------------------- a round

export function RoundPanel({ id, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const navigate = useNavigate()
  const lists = useGolfLists()
  const [r, setR] = useState(null)
  const [version, setVersion] = useState(0)        // a new scorecard draft each time the round comes back from the API
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(false)
  const [course, setCourse] = useState(null)       // its tees, for the details form
  const [confirm, setConfirm] = useState(null)     // 'delete' | 'finish'
  const put = useCallback((next) => { setR(next); setVersion((v) => v + 1) }, [])
  useEffect(() => { api.golfRound(id).then(put).catch((e) => setFailed(e.message)) }, [id, put])
  const courseId = r?.course_id
  useEffect(() => { if (editing && courseId) api.golfCourse(courseId).then(setCourse).catch(() => setCourse({ tees: [] })) }, [editing, courseId])

  if (!r) return <Drawer title="Round" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    if (!course || !lists) return <Drawer title="Round details" onClose={() => setEditing(false)}><p className="muted">Loading...</p></Drawer>
    const fields = [
      { name: 'played_on', label: 'Date', type: 'date', required: true },
      { name: 'tee_id', label: 'Tees', type: 'select', options: course.tees.map((t) => [String(t.tee_id), t.name]) },
      { name: 'holes', label: 'Holes', type: 'select', options: holeChoices(r.course_holes), required: true },
      { name: 'format', label: 'Format', type: 'select', options: lists.formats, required: true },
      { name: 'counts', label: 'Counts for your handicap', type: 'select', options: [['true', 'Yes'], ['false', 'No']], required: true },
      { name: 'handicap', label: 'Your handicap that day', type: 'number', step: 0.1, min: -10, hint: 'Sets the daily handicap (strokes received). A plus handicap is below 0.' },
      { name: 'competition', label: 'Competition', placeholder: 'e.g. Monthly medal' },
      { name: 'partners', label: 'Played with' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ]
    return (
      <FormPanel title="Round details" fields={fields} record={{ ...r, holes: holeSetOf(r.holes) }} onClose={() => setEditing(false)}
        onSave={async (data) => {
          put(await api.updateGolfRound(r.round_id, { ...data, tee_id: data.tee_id == null ? null : Number(data.tee_id), counts: data.counts === 'true' }))
          setEditing(false)
          changed()
        }} />
    )
  }

  const t = r.totals
  const st = r.stats
  const finish = async () => {
    try {
      put(await api.updateGolfRound(r.round_id, { status: 'done' }))
      setConfirm(null)
      changed()
      showToast('Round finished')
    } catch (e) {
      showToast(e.message)
    }
  }
  const remove = async () => {
    try {
      await api.deleteGolfRound(r.round_id)
      changed()
      onClose()
    } catch (e) {
      showToast(e.message)
    }
  }
  const footer = confirm === 'delete' ? (
    <span className="confirm">Remove this round and its scores?
      <button type="button" className="danger" onClick={remove}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(null)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm('delete')}>Remove</button>
    </>
  )
  const sgShown = sgRows(r.sg).length > 0
  const w = r.weather
  return (
    <Drawer title={r.course_name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="section-head">
          <strong>{shortDate(r.played_on)}{r.tee_name && <span className="golf-tee"> · <i className="golf-teedot" style={{ background: r.tee_colour ?? 'var(--faint)' }} />{r.tee_name} tees</span>}</strong>
          <span className={`pill ${r.status === 'playing' ? 'low' : 'ok'}`}>{r.status === 'playing' ? 'Playing' : 'Finished'}</span>
        </div>
        <p className="item-sub">{[r.course_holes === 9 ? '9 holes' : HOLE_SETS[holeSetOf(r.holes)], r.format, r.competition,
          r.partners && `with ${r.partners}`, !r.counts && 'not for handicap'].filter(Boolean).join(' · ')}</p>
        <Numbers items={[
          { label: 'Gross', value: t.gross ?? (t.entered ? `${t.strokes_so_far}` : '—'), sub: t.gross != null ? toPar(t.to_par) : t.to_par_so_far != null ? `${toPar(t.to_par_so_far)} so far` : null },
          { label: 'Stableford', value: `${t.points} pts` },
          t.net != null && { label: 'Net', value: t.net },
          r.daily_handicap != null && { label: 'Daily handicap', value: r.daily_handicap, sub: r.handicap != null ? `from ${hcpText(r.handicap)}` : null },
          t.differential != null && { label: 'Differential', value: num(t.differential), sub: `adjusted ${t.adjusted_gross}` },
        ]} />
        {r.daily_handicap == null && <p className="muted small">No daily handicap: {r.tee_id == null ? 'pick the tees (Edit details)' : r.rating == null
          ? 'the tees need a rating and slope (on the course)' : 'no handicap yet'} - points count with no strokes received.</p>}
        {r.status === 'playing' && (
          <div className="button-row">
            <button type="button" className="primary" onClick={() => { onClose(); navigate(`/golf/play?round=${r.round_id}`) }}>Play on the phone</button>
            {confirm === 'finish' ? (
              <span className="confirm">{t.holes - t.entered} hole{t.holes - t.entered === 1 ? '' : 's'} not filled in. Finish anyway?
                <button type="button" className="secondary" onClick={finish}>Finish</button>
                <button type="button" className="plain" onClick={() => setConfirm(null)}>Cancel</button></span>
            ) : (
              <button type="button" className="secondary" onClick={() => (t.complete ? finish() : setConfirm('finish'))}>Finish</button>
            )}
          </div>
        )}
      </section>
      <section className="panel-section">
        <h3 className="section-title">Scorecard</h3>
        <Scorecard key={version} r={r} onSaved={(next) => { put(next); changed() }} />
      </section>
      {t.entered > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Stats</h3>
          <Numbers items={[
            st.fairway_chances > 0 && { label: 'Fairways', value: `${st.fairways}/${st.fairway_chances}`, sub: st.left || st.right ? `${st.left} left · ${st.right} right` : null },
            st.gir_chances > 0 && { label: 'Greens in reg.', value: `${st.gir}/${st.gir_chances}` },
            st.putt_holes > 0 && { label: 'Putts', value: st.putts, sub: st.three_putts ? `${st.three_putts} three-putt${st.three_putts === 1 ? '' : 's'}` : null },
            st.scramble_chances > 0 && { label: 'Scrambling', value: `${st.scrambles}/${st.scramble_chances}` },
            st.sand_chances > 0 && { label: 'Sand saves', value: `${st.sand_saves}/${st.sand_chances}` },
            { label: 'Penalties', value: st.penalties },
            { label: 'Birdies or better', value: st.birdies + st.eagles },
            { label: 'Pars', value: st.pars },
          ]} />
          {r.shots?.length > 0 && <p className="muted small">{r.shots.length} shot{r.shots.length === 1 ? '' : 's'} marked on the course.</p>}
        </section>
      )}
      {sgShown && (
        <section className="panel-section">
          <h3 className="section-title">Strokes gained</h3>
          <StrokesGained sg={r.sg} />
        </section>
      )}
      {(w || r.notes) && (
        <section className="panel-section">
          {w && <p className="golf-weather"><span aria-hidden="true">{w.icon}</span> {[w.sky, w.max != null && `${Math.round(w.max)}° / ${Math.round(w.min)}°`,
            w.rain_mm ? `${w.rain_mm} mm rain` : null].filter(Boolean).join(' · ')}</p>}
          {r.notes && <p className="small golf-notes">{r.notes}</p>}
        </section>
      )}
      <p className="muted small golf-more">
        <button type="button" className="link-plain" onClick={() => { onClose(); openPanel('golfcourse', { id: r.course_id }) }}>{r.course_name}: the course →</button>
      </p>
    </Drawer>
  )
}

// The scorecard grid, typed in place: score (P = picked up), putts, fairway, penalties; points worked out as you type.
// Only the holes you changed are sent ("Save card").
const draftOf = (h) => ({ strokes: h.picked_up ? 'P' : h.strokes != null ? String(h.strokes) : '', putts: h.putts != null ? String(h.putts) : '',
  fairway: h.fairway ?? '', penalties: h.penalties ? String(h.penalties) : '' })
const pointsOf = (h, d) => (d.strokes === '' ? null : d.strokes === 'P' ? 0 : Math.max(0, h.par + h.received - Number(d.strokes) + 2))
const STROKES = Array.from({ length: 20 }, (_, i) => String(i + 1))
const FAIRWAY = [['hit', 'Hit'], ['left', 'Left'], ['right', 'Right'], ['short', 'Short'], ['long', 'Long']]

// One hole's row of the scorecard: number (a dot per stroke received), index, par, metres, then the choices.
function HoleRow({ h, d, set }) {
  const pts = pointsOf(h, d)
  const diff = d.strokes !== '' && d.strokes !== 'P' ? Number(d.strokes) - h.par : null
  return (
    <tr>
      <th scope="row">{h.hole_no}{h.received > 0 && <span className="golf-sc-dots" title={`${h.received} stroke${h.received > 1 ? 's' : ''} received`}>{'•'.repeat(h.received)}</span>}</th>
      <td className="muted">{h.stroke_index ?? ''}</td>
      <td>{h.par}</td>
      <td className="golf-sc-m muted">{h.metres ?? ''}</td>
      <td className={diff == null ? undefined : diff < 0 ? 'golf-sc-under' : diff > 0 ? 'golf-sc-over' : undefined}>
        <select value={d.strokes} onChange={set(h.hole_no, 'strokes')} aria-label={`Hole ${h.hole_no} score`}>
          <option value="">–</option>
          {STROKES.map((n) => <option key={n} value={n}>{n}</option>)}
          <option value="P">P</option>
        </select>
      </td>
      <td>
        <select value={d.putts} onChange={set(h.hole_no, 'putts')} aria-label={`Hole ${h.hole_no} putts`} disabled={d.strokes === 'P'}>
          <option value="">–</option>
          {['0', '1', '2', '3', '4', '5', '6'].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </td>
      <td>
        {h.par >= 4 ? (
          <select value={d.fairway} onChange={set(h.hole_no, 'fairway')} aria-label={`Hole ${h.hole_no} fairway`}>
            <option value="">–</option>
            {FAIRWAY.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        ) : <span className="muted" title="Par 3: no fairway">·</span>}
      </td>
      <td>
        <select value={d.penalties} onChange={set(h.hole_no, 'penalties')} aria-label={`Hole ${h.hole_no} penalty strokes`}>
          <option value="">0</option>
          {['1', '2', '3', '4'].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </td>
      <td className="golf-sc-pts">{pts ?? ''}</td>
    </tr>
  )
}

function Scorecard({ r, onSaved }) {
  const [draft, setDraft] = useState(() => Object.fromEntries(r.holes.map((h) => [h.hole_no, draftOf(h)])))
  const [dirty, setDirty] = useState(() => new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (no, k) => (e) => {
    const v = e.target.value
    setDraft((d) => ({ ...d, [no]: { ...d[no], [k]: v, ...(k === 'strokes' && v === 'P' ? { putts: '' } : {}) } }))
    setDirty((s) => new Set(s).add(no))
  }
  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const holes = r.holes.filter((h) => dirty.has(h.hole_no)).map((h) => {
        const d = draft[h.hole_no]
        return { hole_no: h.hole_no, strokes: d.strokes === '' || d.strokes === 'P' ? null : Number(d.strokes), picked_up: d.strokes === 'P',
          putts: d.putts === '' ? null : Number(d.putts), fairway: d.fairway || null, penalties: Number(d.penalties) || 0,
          sand: h.sand ?? 0, first_putt_m: h.first_putt_m }
      })
      onSaved(await api.saveGolfScorecard(r.round_id, holes))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const nines = r.holes.length > 9 ? [['Out', r.holes.slice(0, 9)], ['In', r.holes.slice(9)]] : [[null, r.holes]]
  const sum = (hs) => {
    const ds = hs.map((h) => draft[h.hole_no])
    const scored = ds.filter((d) => d.strokes !== '' && d.strokes !== 'P')
    return {
      par: hs.reduce((a, h) => a + h.par, 0), metres: hs.every((h) => h.metres) ? hs.reduce((a, h) => a + h.metres, 0) : null,
      strokes: scored.length ? scored.reduce((a, d) => a + Number(d.strokes), 0) : null, all: scored.length === hs.length,
      putts: ds.some((d) => d.putts !== '') ? ds.reduce((a, d) => a + (Number(d.putts) || 0), 0) : null,
      points: hs.reduce((a, h) => a + (pointsOf(h, draft[h.hole_no]) ?? 0), 0),
    }
  }
  const sumRow = (label, hs, total = false) => {
    const s = sum(hs)
    return (
      <tr key={label} className={total ? 'golf-sc-total' : 'golf-sc-sum'}>
        <th scope="row" colSpan={2}>{label}</th>
        <td>{s.par}</td><td className="golf-sc-m">{s.metres ?? ''}</td>
        <td>{s.strokes ?? ''}{s.strokes != null && !s.all && <span className="muted">*</span>}</td>
        <td>{s.putts ?? ''}</td><td /><td /><td>{s.points}</td>
      </tr>
    )
  }
  return (
    <>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="golf-table-wrap golf-sc-wrap" role="region" aria-label="Scorecard (scrolls sideways)" tabIndex={0}>
        <table className="golf-table golf-scorecard">
          <thead>
            <tr><th scope="col">Hole</th><th scope="col"><abbr title="Stroke index">SI</abbr></th><th scope="col">Par</th>
              <th scope="col" className="golf-sc-m">m</th><th scope="col">Score</th><th scope="col">Putts</th><th scope="col">Fairway</th>
              <th scope="col"><abbr title="Penalty strokes">Pen.</abbr></th><th scope="col"><abbr title="Stableford points">Pts</abbr></th></tr>
          </thead>
          <tbody>
            {nines.flatMap(([label, hs]) => [
              ...hs.map((h) => <HoleRow key={h.hole_no} h={h} d={draft[h.hole_no]} set={set} />),
              label ? sumRow(label, hs) : null,
            ])}
            {sumRow('Total', r.holes, true)}
          </tbody>
        </table>
      </div>
      <p className="muted small">P: picked up (0 points; it counts as net double bogey for your handicap). A dot by the hole: a stroke
        received. *: not every hole has a score yet.</p>
      <div className="button-row">
        <button type="button" className="primary" onClick={save} disabled={busy || dirty.size === 0}>{busy ? 'Saving...' : 'Save card'}</button>
        {dirty.size > 0 && <span className="muted small">{dirty.size} hole{dirty.size === 1 ? '' : 's'} changed</span>}
      </div>
    </>
  )
}

// ---------------------------------------------------------------- a new round

// day: the calendar event's day (Log it).
export function NewRoundPanel({ courseId = null, day = null, onClose }) {
  const { changed, openPanel, showToast } = useApp()
  const navigate = useNavigate()
  const courses = useGolfCourses()
  const lists = useGolfLists()
  const [picked, setPicked] = useState(courseId != null ? String(courseId) : '')
  const [detail, setDetail] = useState(null)
  const [f, setF] = useState({ tee_id: '', holes: '18', format: 'Stableford', played_on: day ?? today(), competition: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const course = picked || (courses?.[0] ? String(courses[0].course_id) : '')
  useEffect(() => {
    if (!course) return
    api.golfCourse(course).then((c) => {
      setDetail(c)
      // the tees you played from last time there, else the first with a rating, else the first
      const lastTee = c.tees.find((t) => t.name === c.recent[0]?.tee_name) ?? c.tees.find((t) => t.rating != null) ?? c.tees[0]
      setF((x) => ({ ...x, tee_id: lastTee ? String(lastTee.tee_id) : '', holes: c.holes === 9 ? 'front' : x.holes === 'front' && c.holes === 18 ? '18' : x.holes }))
    }).catch((e) => setError(e.message))
  }, [course])
  if (!courses || !lists) return <Drawer title="Start a round" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  if (!courses.length) {
    return (
      <Drawer title="Start a round" onClose={onClose}>
        <p>First, add your course: OpenStreetMap has most of them, with every hole drawn.</p>
        <div className="button-row">
          <button type="button" className="primary" onClick={() => { onClose(); openPanel('golffind', {}) }}>Find your course</button>
        </div>
      </Drawer>
    )
  }
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const tee = detail?.tees.find((t) => String(t.tee_id) === f.tee_id)
  const start = async (live) => {
    setBusy(true)
    setError('')
    try {
      const made = await api.addGolfRound({ course_id: Number(course), tee_id: f.tee_id ? Number(f.tee_id) : null, holes: f.holes,
        format: f.format, played_on: f.played_on || today(), competition: f.competition.trim() || null })
      changed()
      onClose()
      if (live) navigate(`/golf/play?round=${made.round_id}`)
      else openPanel('golfround', { id: made.round_id })
    } catch (e) {
      setError(e.message)
      setBusy(false)
      showToast(e.message)
    }
  }
  const ready = detail && String(detail.course_id) === course
  const footer = (
    <>
      <button type="button" className="primary" disabled={busy || !ready} onClick={() => start(true)}>Play now</button>
      <button type="button" className="secondary" disabled={busy || !ready} onClick={() => start(false)}>Type in a card</button>
      <span className="spacer" />
      <button type="button" className="plain" onClick={onClose}>Cancel</button>
    </>
  )
  return (
    <Drawer title="Start a round" onClose={onClose} footer={footer}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="golf-form-grid">
        <label className="field golf-wide">Course
          <select value={course} onChange={(e) => setPicked(e.target.value)}>
            {courses.map((c) => <option key={c.course_id} value={c.course_id}>{c.name}{c.last_played ? '' : ' (not played yet)'}</option>)}
          </select></label>
        <label className="field">Tees
          <select value={f.tee_id} onChange={set('tee_id')} disabled={!ready}>
            <option value="">{ready && !detail.tees.length ? 'None added yet' : '—'}</option>
            {(ready ? detail.tees : []).map((t) => <option key={t.tee_id} value={t.tee_id}>{t.name}{t.metres ? ` (${t.metres.toLocaleString()} m)` : ''}</option>)}
          </select></label>
        <label className="field">Holes
          <select value={f.holes} onChange={set('holes')}>
            {holeChoices(ready ? detail.holes : 18).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select></label>
        <label className="field">Format
          <select value={f.format} onChange={set('format')}>
            {lists.formats.map((x) => <option key={x} value={x}>{x}</option>)}
          </select></label>
        <label className="field">Date<input type="date" value={f.played_on} onChange={set('played_on')} required /></label>
        <label className="field golf-wide">Competition<input value={f.competition} onChange={set('competition')} placeholder="e.g. Saturday stableford" /></label>
      </div>
      {ready && (
        <p className="muted small">
          {tee?.daily_handicap != null && f.holes === '18' ? <>Daily handicap from the {tee.name} tees: <strong>{tee.daily_handicap}</strong>. </>
            : tee && tee.rating == null ? `The ${tee.name} tees have no rating or slope yet: add them on the course for a daily handicap and points with strokes. `
              : !detail.tees.length ? 'Add the course\'s tees (with their rating and slope) for a daily handicap and lengths. ' : ''}
          {f.format === 'Ambrose' && 'A team format: it won\'t count for your handicap. '}
          "Play now" opens the round on your phone: distances to the green and your score as you go.
        </p>
      )}
    </Drawer>
  )
}
