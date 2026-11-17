import { useCallback, useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { GolfIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { Numbers } from './golfCards.jsx'
import { holeSketch, nineLabel, num, parsePars, plural, toPar } from './golfFormat.js'
import { useGolfCourses, useGolfSettings } from './golfParts.jsx'

// Golf's courses: the list; a course (details, tees with rating / slope / each hole's metres, the holes' pars and
// stroke indexes, a sketch of each mapped hole, how you play each hole, recent rounds there); finding one on
// OpenStreetMap (by place or near you) or adding one by hand. Maps © OpenStreetMap contributors (ODbL).

const OSM_NOTE = 'Course maps © OpenStreetMap contributors.'

export function CoursesView() {
  const { openPanel } = useApp()
  const courses = useGolfCourses()
  const settings = useGolfSettings()
  return (
    <section className="page golf">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('golffind', {})}>Find a course</button>
      </div>
      {!courses ? <p className="muted loading">Loading...</p> : courses.length === 0 ? (
        <EmptyState Icon={GolfIcon} title="No courses yet" action="Find your course" onAction={() => openPanel('golffind', {})}>
          Search OpenStreetMap by place or near you - most courses come with every hole drawn - or add one by hand.</EmptyState>
      ) : (
        <section className="card home-card">
          <ul className="list plain-list">
            {courses.map((c) => (
              <li key={c.course_id}>
                <button type="button" className="row-button" onClick={() => openPanel('golfcourse', { id: c.course_id })}>
                  <span className="stat-icon ok" aria-hidden="true"><GolfIcon size={18} /></span>
                  <span className="grow">
                    <span className="item-title">{c.name}{settings?.home_course_id === c.course_id && <span className="pill ok golf-home-pill">Home</span>}</span>
                    <span className="item-meta">{[c.place, `${c.holes} holes, par ${c.par}`, plural(c.rounds, 'round'),
                      c.best != null && `best ${c.best}`, c.average != null && `average ${num(c.average)}`,
                      c.mapped ? `${c.mapped} of ${c.holes} holes mapped` : null,
                      c.rated ? plural(c.rated, 'rated tee') : 'no rated tees'].filter(Boolean).join(' · ')}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="muted small">{OSM_NOTE}</p>
        </section>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- a course

export function CoursePanel({ id, onClose }) {
  const { changed, showToast, openPanel } = useApp()
  const settings = useGolfSettings()
  const [c, setC] = useState(null)
  const [version, setVersion] = useState(0)
  const [failed, setFailed] = useState('')
  const [editing, setEditing] = useState(false)
  const [tee, setTee] = useState(null)              // the tee being edited: {} = a new one
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const put = useCallback((next) => { setC(next); setVersion((v) => v + 1) }, [])
  useEffect(() => { api.golfCourse(id).then(put).catch((e) => setFailed(e.message)) }, [id, put])
  if (!c) return <Drawer title="Course" onClose={onClose}>{failed ? <p className="alert error">{failed}</p> : <p className="muted">Loading...</p>}</Drawer>

  if (editing) {
    const fields = [
      { name: 'name', label: 'Name', required: true },
      { name: 'place', label: 'Where', placeholder: 'e.g. Herston, QLD' },
      { name: 'holes', label: 'Holes', type: 'select', options: [['18', '18'], ['9', '9']], required: true },
      { name: 'website', label: 'Website', type: 'url' },
      { name: 'notes', label: 'Notes', type: 'textarea' },
    ]
    return (
      <FormPanel title="Course details" fields={fields} record={c} onClose={() => setEditing(false)}
        onSave={async (data) => { put(await api.updateGolfCourse(c.course_id, { ...data, holes: Number(data.holes) })); setEditing(false); changed() }} />
    )
  }
  const run = async (fn, done) => {
    setBusy(true)
    try {
      await fn()
      if (done) showToast(done)
    } catch (e) {
      showToast(e.message)
    }
    setBusy(false)
  }
  const isHome = settings?.home_course_id === c.course_id
  const remove = () => run(async () => { await api.deleteGolfCourse(c.course_id); changed(); onClose() })
  const footer = confirm ? (
    <span className="confirm">Remove {c.name}?
      <button type="button" className="danger" onClick={() => { setConfirm(false); remove() }}>Remove</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      <button type="button" className="primary" onClick={() => { onClose(); openPanel('golfnewround', { courseId: c.course_id }) }}>Start a round here</button>
      <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>Remove</button>
    </>
  )
  const played = c.holes_list.filter((h) => h.you)
  const hardest = [...played].sort((a, b) => b.you.vs_par - a.you.vs_par).slice(0, 3).filter((h) => h.you.vs_par > 0)
  const mapped = c.holes_list.filter((h) => h.map?.line?.length > 1)
  return (
    <Drawer title={c.name} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <p className="item-sub">{[c.place, `${c.holes} holes`, `par ${c.par}`, c.mapped ? `${c.mapped} holes mapped` : 'no map'].filter(Boolean).join(' · ')}</p>
        {c.you.rounds > 0 && (
          <Numbers items={[
            { label: 'Your rounds', value: c.you.rounds },
            c.you.best != null && { label: 'Best', value: c.you.best, sub: toPar(c.you.best - c.par) },
            c.you.average != null && { label: 'Average', value: num(c.you.average) },
            c.you.best_points != null && { label: 'Best points', value: c.you.best_points },
          ]} />
        )}
        {c.notes && <p className="small golf-notes">{c.notes}</p>}
        <div className="button-row">
          {isHome ? <span className="pill ok">Your home course</span> : (
            <button type="button" className="secondary small" disabled={busy}
              onClick={() => run(async () => { await api.saveGolfSettings({ home_course_id: c.course_id }); changed() }, 'Home course set')}>
              Set as home course</button>
          )}
          {c.osm && (
            <button type="button" className="plain small" disabled={busy}
              onClick={() => run(async () => { put(await api.importGolfCourse(c.osm)); changed() }, 'Map refreshed from OpenStreetMap')}>
              {busy ? 'Working...' : 'Refresh map from OpenStreetMap'}</button>
          )}
          {c.website && <a className="button plain small" href={c.website} target="_blank" rel="noreferrer">Website</a>}
        </div>
      </section>

      <section className="panel-section">
        <div className="section-head">
          <h3 className="section-title">Tees</h3>
          {!tee && <button type="button" className="plain small" onClick={() => setTee({})}>+ Add tees</button>}
        </div>
        {c.tees.length === 0 && !tee && <p className="muted small">Add the tees you play from with Golf Australia's rating and slope
          (on the scorecard or GolfLink): they give your daily handicap, Stableford strokes and a differential for your handicap.</p>}
        <ul className="golf-tees">
          {c.tees.map((t) => (tee?.tee_id === t.tee_id ? null : (
            <li key={t.tee_id}>
              <i className="golf-teedot big" style={{ background: t.colour ?? 'var(--faint)' }} aria-hidden="true" />
              <span className="grow">
                <span className="item-title">{t.name}{t.gender && <span className="muted small"> · {t.gender}</span>}</span>
                <span className="item-meta">{[t.rating != null && t.slope ? `rating ${num(t.rating)} / slope ${t.slope}` : 'no rating or slope',
                  t.metres && `${t.metres.toLocaleString()} m`].filter(Boolean).join(' · ')}</span>
              </span>
              {t.daily_handicap != null && <span className="golf-daily" title="Your daily handicap from these tees">Daily <strong>{t.daily_handicap}</strong></span>}
              <button type="button" className="plain small" onClick={() => setTee(t)}>Edit</button>
            </li>
          )))}
        </ul>
        {tee && <TeeForm key={tee.tee_id ?? 'new'} c={c} tee={tee} onDone={(next) => { if (next) { put(next); changed() } setTee(null) }} />}
      </section>

      <section className="panel-section">
        <h3 className="section-title">Holes</h3>
        <HolesTable key={version} c={c} onSaved={(next) => { put(next); changed() }} />
        {hardest.length > 0 && (
          <p className="small golf-hardest">Your hardest: {hardest.map((h) => `hole ${h.hole_no} (${toPar(Math.round(h.you.vs_par * 10) / 10)} on average)`).join(', ')}.</p>
        )}
      </section>

      {mapped.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">The holes, drawn</h3>
          <ul className="golf-sketches">
            {mapped.map((h) => <li key={h.hole_no}><HoleMap hole={h} /></li>)}
          </ul>
          <p className="muted small">{OSM_NOTE} Tee at the bottom, green at the top.</p>
        </section>
      )}

      {c.recent.length > 0 && (
        <section className="panel-section">
          <h3 className="section-title">Your rounds here</h3>
          <ul className="list plain-list">
            {c.recent.map((r) => (
              <li key={r.round_id}>
                <button type="button" className="row-button" onClick={() => { onClose(); openPanel('golfround', { id: r.round_id }) }}>
                  <span className="grow"><span className="item-title">{shortDate(r.played_on)}</span>
                    <span className="item-meta">{[r.tee_name, nineLabel(r.holes)].filter(Boolean).join(' · ')}</span></span>
                  <span className="golf-round-score"><strong>{r.gross != null ? `${r.gross} (${toPar(r.to_par)})` : `${r.points} pts`}</strong>
                    {r.gross != null && <span className="muted small">{r.points} pts</span>}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Drawer>
  )
}

// A hole drawn from its OpenStreetMap shapes: fairways, water, bunkers, the tees and green, the hole's line.
export function HoleMap({ hole }) {
  const s = holeSketch(hole.map)
  if (!s) return null
  return (
    <figure className="golf-sketch">
      <svg viewBox={s.viewBox} role="img" aria-label={`Hole ${hole.hole_no}, par ${hole.par}: map`} preserveAspectRatio="xMidYMid meet">
        <rect className="golf-sketch-rough" x={s.viewBox.split(' ')[0]} y={s.viewBox.split(' ')[1]} width={s.width} height={s.height} />
        {s.fairways.map((d, i) => <path key={`f${i}`} className="golf-sketch-fairway" d={d} />)}
        {s.water.map((d, i) => <path key={`w${i}`} className="golf-sketch-water" d={d} />)}
        {s.bunkers.map((d, i) => <path key={`b${i}`} className="golf-sketch-bunker" d={d} />)}
        {s.tees.map((d, i) => <path key={`t${i}`} className="golf-sketch-tee" d={d} />)}
        {s.green && <path className="golf-sketch-green" d={s.green} />}
        <path className="golf-sketch-line" d={s.line} />
      </svg>
      <figcaption><strong>{hole.hole_no}</strong> · par {hole.par}{hole.stroke_index ? ` · SI ${hole.stroke_index}` : ''}</figcaption>
    </figure>
  )
}

// Every hole's par and stroke index, editable; with the first tees' metres and how you play each hole.
function HolesTable({ c, onSaved }) {
  const [rows, setRows] = useState(() => c.holes_list.map((h) => ({ hole_no: h.hole_no, par: String(h.par), si: h.stroke_index != null ? String(h.stroke_index) : '' })))
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lengths = c.tees.find((t) => t.metres)
  const set = (i, k) => (e) => { const v = e.target.value; setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r))); setDirty(true) }
  const save = async () => {
    setError('')
    const sis = rows.map((r) => r.si).filter(Boolean)
    if (new Set(sis).size !== sis.length) { setError('Each stroke index can be used once.'); return }
    setBusy(true)
    try {
      onSaved(await api.saveGolfHoles(c.course_id, rows.map((r) => ({ hole_no: r.hole_no, par: Number(r.par), stroke_index: r.si ? Number(r.si) : null }))))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const you = Object.fromEntries(c.holes_list.map((h) => [h.hole_no, h.you]))
  const anyYou = c.holes_list.some((h) => h.you)
  return (
    <>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="golf-table-wrap" tabIndex={0} role="region" aria-label="Holes (scrolls sideways)">
        <table className="golf-table golf-holes">
          <thead><tr><th scope="col">Hole</th><th scope="col">Par</th><th scope="col"><abbr title="Stroke index">SI</abbr></th>
            {lengths && <th scope="col">m ({lengths.name})</th>}
            {anyYou && <><th scope="col">You</th><th scope="col">vs par</th><th scope="col"><abbr title="Par or better">Par+</abbr></th><th scope="col">Pts</th></>}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => {
              const y = you[r.hole_no]
              return (
                <tr key={r.hole_no}>
                  <th scope="row">{r.hole_no}</th>
                  <td><select value={r.par} onChange={set(i, 'par')} aria-label={`Hole ${r.hole_no} par`}>
                    {['3', '4', '5', '6'].map((p) => <option key={p} value={p}>{p}</option>)}</select></td>
                  <td><select value={r.si} onChange={set(i, 'si')} aria-label={`Hole ${r.hole_no} stroke index`}>
                    <option value="">–</option>
                    {Array.from({ length: 18 }, (_, k) => String(k + 1)).map((n) => <option key={n} value={n}>{n}</option>)}</select></td>
                  {lengths && <td className="muted">{lengths.lengths[r.hole_no] ?? ''}</td>}
                  {anyYou && (y ? <>
                    <td>{num(y.average)}</td>
                    <td className={y.vs_par > 0.5 ? 'golf-sc-over' : y.vs_par < 0 ? 'golf-sc-under' : undefined}>{toPar(Math.round(y.vs_par * 10) / 10)}</td>
                    <td>{y.par_or_better}%</td><td>{num(y.points)}</td>
                  </> : <><td /><td /><td /><td /></>)}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="button-row">
        <button type="button" className="secondary small" onClick={save} disabled={!dirty || busy}>{busy ? 'Saving...' : 'Save pars and indexes'}</button>
        <span className="muted small">Stroke index: 1 is the hardest hole (where you get your first stroke).</span>
      </div>
    </>
  )
}

const COLOURS = [['#1f4fbf', 'Blue'], ['#f2f2f2', 'White'], ['#d02b2b', 'Red'], ['#e8c21a', 'Yellow'], ['#222222', 'Black'], ['#2f8f46', 'Green'], ['#c9a227', 'Gold']]

// A set of tees: name, colour, rating, slope, and each hole's metres.
function TeeForm({ c, tee, onDone }) {
  const [f, setF] = useState(() => ({
    name: tee.name ?? '', colour: tee.colour ?? '#1f4fbf', gender: tee.gender ?? '', rating: tee.rating != null ? String(Number(tee.rating)) : '',
    slope: tee.slope != null ? String(tee.slope) : '',
    lengths: Object.fromEntries(c.holes_list.map((h) => [h.hole_no, tee.lengths?.[h.hole_no] != null ? String(tee.lengths[h.hole_no]) : ''])),
  }))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const setLen = (no) => (e) => { const v = e.target.value; setF((x) => ({ ...x, lengths: { ...x.lengths, [no]: v } })) }
  const total = Object.values(f.lengths).reduce((a, v) => a + (Number(v) || 0), 0)
  const save = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    const lengths = Object.fromEntries(Object.entries(f.lengths).map(([no, v]) => [no, v === '' ? null : Number(v)]))
    const data = { name: f.name.trim(), colour: f.colour, gender: f.gender || null, rating: f.rating === '' ? null : Number(f.rating),
      slope: f.slope === '' ? null : Number(f.slope), lengths }
    try {
      onDone(tee.tee_id ? await api.updateGolfTee(tee.tee_id, data) : await api.addGolfTee(c.course_id, data))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  const remove = async () => {
    try {
      await api.deleteGolfTee(tee.tee_id)
      onDone(await api.golfCourse(c.course_id))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="golf-tee-form" onSubmit={save}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="golf-form-grid">
        <label className="field">Name<input value={f.name} onChange={set('name')} required maxLength={40} placeholder="e.g. Blue" /></label>
        <label className="field">Colour
          <select value={f.colour} onChange={set('colour')}>
            {COLOURS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            {!COLOURS.some(([v]) => v === f.colour) && <option value={f.colour}>{f.colour}</option>}
          </select></label>
        <label className="field">For
          <select value={f.gender} onChange={set('gender')}><option value="">—</option><option>Men</option><option>Women</option></select></label>
        <label className="field">Course rating<input type="number" inputMode="decimal" step="0.1" min="25" max="85" value={f.rating} onChange={set('rating')} placeholder="e.g. 71.0" /></label>
        <label className="field">Slope<input type="number" inputMode="numeric" min="55" max="155" value={f.slope} onChange={set('slope')} placeholder="e.g. 125" /></label>
      </div>
      <fieldset className="golf-lengths">
        <legend>Each hole's metres{total ? ` (${total.toLocaleString()} m)` : ''}</legend>
        {c.holes_list.map((h) => (
          <label key={h.hole_no} className="golf-length">{h.hole_no}
            <input type="number" inputMode="numeric" min="30" max="800" value={f.lengths[h.hole_no]} onChange={setLen(h.hole_no)}
              aria-label={`Hole ${h.hole_no} metres`} /></label>
        ))}
      </fieldset>
      <div className="button-row">
        <button type="submit" className="primary small" disabled={busy}>Save tees</button>
        <button type="button" className="plain small" onClick={() => onDone(null)}>Cancel</button>
        {tee.tee_id && (confirm ? (
          <span className="confirm">Remove these tees? Rounds keep their scores.
            <button type="button" className="danger small" onClick={remove}>Remove</button>
            <button type="button" className="plain small" onClick={() => setConfirm(false)}>Cancel</button></span>
        ) : <button type="button" className="plain small destructive" onClick={() => setConfirm(true)}>Remove</button>)}
      </div>
    </form>
  )
}

// ---------------------------------------------------------------- finding a course

export function FindCoursePanel({ onClose }) {
  const { changed, openPanel } = useApp()
  const [q, setQ] = useState('')
  const [found, setFound] = useState(null)        // {place, courses}
  const [busy, setBusy] = useState('')            // 'search' | 'near' | an osm id being added
  const [error, setError] = useState('')
  const look = async (params, kind) => {
    setBusy(kind)
    setError('')
    try {
      setFound(await api.golfFindCourses(params))
    } catch (e) {
      setError(e.message)
    }
    setBusy('')
  }
  const near = () => {
    if (!navigator.geolocation) { setError("This browser can't tell where you are: search by place instead."); return }
    setBusy('near')
    setError('')
    navigator.geolocation.getCurrentPosition(
      (p) => look({ lat: p.coords.latitude.toFixed(5), lon: p.coords.longitude.toFixed(5) }, 'near'),
      () => { setBusy(''); setError("Couldn't get your location (allowed in the browser? on HTTPS?). Search by place instead.") },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 })
  }
  const open = (courseId) => { onClose(); openPanel('golfcourse', { id: courseId }) }
  const add = async (osm) => {
    setBusy(osm)
    setError('')
    try {
      const c = await api.importGolfCourse(osm)
      changed()
      open(c.course_id)
    } catch (e) {
      setError(e.message)
      setBusy('')
    }
  }
  return (
    <Drawer title="Find a course" onClose={onClose}>
      {error && <p className="alert error" role="alert">{error}</p>}
      <form className="golf-find" onSubmit={(e) => { e.preventDefault(); if (q.trim().length >= 2) look({ q: q.trim() }, 'search') }}>
        <label className="field golf-find-q">Town or suburb
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Herston" minLength={2} /></label>
        <button type="submit" className="primary" disabled={!!busy || q.trim().length < 2}>{busy === 'search' ? 'Looking...' : 'Search'}</button>
        <button type="button" className="secondary" onClick={near} disabled={!!busy}>{busy === 'near' ? 'Looking...' : 'Near me'}</button>
      </form>
      {found && (
        <section className="golf-found">
          <p className="muted small">{found.courses.length ? `${plural(found.courses.length, 'course')} within 25 km${found.place ? ` of ${found.place}` : ''}`
            : found.place ? `No courses mapped within 25 km of ${found.place}.` : 'No place by that name.'}</p>
          <ul className="list plain-list">
            {found.courses.map((x) => (
              <li key={x.osm} className="golf-found-row">
                <span className="grow">
                  <span className="item-title">{x.name}</span>
                  <span className="item-meta">{[x.place, x.metres != null && `${num(x.metres / 1000)} km away`].filter(Boolean).join(' · ')}</span>
                </span>
                {x.course_id ? <button type="button" className="plain small" onClick={() => open(x.course_id)}>Already added</button>
                  : <button type="button" className="primary small" disabled={!!busy} onClick={() => add(x.osm)}>{busy === x.osm ? 'Adding...' : 'Add'}</button>}
              </li>
            ))}
          </ul>
          <p className="muted small">{OSM_NOTE} Adding one brings its holes (par, stroke index, map) where they're mapped; add the tees'
            rating and slope yourself (from the scorecard or GolfLink).</p>
        </section>
      )}
      <ByHand onAdded={(c) => { changed(); open(c.course_id) }} />
    </Drawer>
  )
}

function ByHand({ onAdded }) {
  const [openForm, setOpenForm] = useState(false)
  const [f, setF] = useState({ name: '', place: '', holes: '18', pars: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  if (!openForm) return <button type="button" className="plain golf-by-hand" onClick={() => setOpenForm(true)}>Not there? Add a course by hand</button>
  const save = async (e) => {
    e.preventDefault()
    setError('')
    const pars = parsePars(f.pars, Number(f.holes))
    if (pars === null) { setError(`Type ${f.holes} pars (3 to 6), or leave them blank (every hole a par 4, to fix after).`); return }
    setBusy(true)
    try {
      onAdded(await api.addGolfCourse({ name: f.name.trim(), place: f.place.trim() || null, holes: Number(f.holes), pars: pars.length ? pars : null }))
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <form className="panel-section golf-by-hand-form" onSubmit={save}>
      <h3 className="section-title">Add a course by hand</h3>
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="golf-form-grid">
        <label className="field">Name<input value={f.name} onChange={set('name')} required maxLength={120} /></label>
        <label className="field">Where<input value={f.place} onChange={set('place')} placeholder="e.g. Herston, QLD" /></label>
        <label className="field">Holes<select value={f.holes} onChange={set('holes')}><option value="18">18</option><option value="9">9</option></select></label>
        <label className="field golf-wide">Pars, in order (optional)
          <input value={f.pars} onChange={set('pars')} inputMode="numeric" placeholder="e.g. 4 4 3 5 4 4 3 4 5 ..." /></label>
      </div>
      <div className="button-row"><button type="submit" className="primary small" disabled={busy || !f.name.trim()}>Add the course</button></div>
    </form>
  )
}
