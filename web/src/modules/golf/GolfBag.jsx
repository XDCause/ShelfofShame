import { useEffect, useState } from 'react'
import { api, shortDate, today } from '../../api.js'
import { BarList } from '../../components/charts.jsx'
import Drawer from '../../components/Drawer.jsx'
import { TargetIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { FormPanel } from '../volleyball/VolleyballPanels.jsx'
import { Numbers } from './golfCards.jsx'
import { plural } from './golfFormat.js'
import { useGolfLists } from './golfParts.jsx'

// Golf's bag (each club: the carry you'd say, and what your marked shots measured - a bar per club, to see the gaps)
// and practice (sessions, minutes by kind, drills with their best and last score).

// ---------------------------------------------------------------- the bag

export function BagView() {
  const { refreshKey, openPanel, changed, showToast } = useApp()
  const [clubs, setClubs] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.golfClubs().then(setClubs).catch((e) => setError(e.message)) }, [refreshKey])
  const fill = async () => {
    try {
      setClubs(await api.golfStandardBag())
      changed()
      showToast('A standard bag is in: tap a club to make its carry yours.')
    } catch (e) {
      showToast(e.message)
    }
  }
  const toggle = async (c) => {
    try {
      setClubs(await api.updateGolfClub(c.club_id, { in_bag: !c.in_bag }))
      changed()
    } catch (e) {
      showToast(e.message)
    }
  }
  if (error) return <p className="alert error">{error}</p>
  if (!clubs) return <p className="muted loading">Loading...</p>
  const inBag = clubs.filter((c) => c.in_bag)
  return (
    <section className="page golf">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('golfclub', {})}>+ Add a club</button>
      </div>
      {clubs.length === 0 ? (
        <EmptyState Icon={TargetIcon} title="Your bag is empty" action="Fill a standard bag" onAction={fill}>
          Start from a typical set of 13 clubs with mid-handicap carries, then make each one yours - or add your clubs one by one.
          Shots you mark on the course with a club measure its real distance.</EmptyState>
      ) : (
        <div className="home-grid">
          <section className="card home-card">
            <h2 className="home-card-title">Distances</h2>
            <Gapping clubs={inBag} />
          </section>
          <section className="card home-card">
            <h2 className="home-card-title">Clubs <span className="muted small">{inBag.length} in the bag{inBag.length > 14 ? ' (the rules allow 14)' : ''}</span></h2>
            <ul className="golf-clubs">
              {clubs.map((c) => (
                <li key={c.club_id} className={c.in_bag ? undefined : 'golf-out-of-bag'}>
                  <button type="button" className="row-button" onClick={() => openPanel('golfclub', { id: c.club_id, club: c })}>
                    <span className="grow">
                      <span className="item-title">{c.name}</span>
                      <span className="item-meta">{[c.kind, c.loft != null && `${Number(c.loft)}°`, c.carry_m && `carry ${c.carry_m} m`,
                        c.measured && `measured ${c.measured.average} m (${plural(c.measured.shots, 'shot')})`, c.brand].filter(Boolean).join(' · ')}</span>
                    </span>
                  </button>
                  <label className="golf-in-bag"><input type="checkbox" checked={c.in_bag} onChange={() => toggle(c)} /> In bag</label>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </section>
  )
}

// A bar per club (not the putter): your carry, and the measured middle half of your shots as a band with its average.
function Gapping({ clubs }) {
  const rows = clubs.filter((c) => c.kind !== 'Putter' && (c.carry_m || c.measured))
  if (!rows.length) return <p className="muted small">Give your clubs a carry (tap one) to see the gaps between them.</p>
  const max = Math.max(...rows.map((c) => Math.max(c.carry_m ?? 0, c.measured?.longest ?? 0)))
  const at = (m) => `${(100 * m) / max}%`
  return (
    <>
      <ul className="golf-gaps">
        {rows.map((c) => (
          <li key={c.club_id}>
            <span className="golf-gap-name">{c.name}</span>
            <span className="golf-gap-track" aria-hidden="true">
              {c.carry_m && <span className="golf-gap-carry" style={{ width: at(c.carry_m) }} />}
              {c.measured && <span className="golf-gap-band" style={{ left: at(c.measured.short), width: `calc(${at(c.measured.long - c.measured.short)} + 3px)` }} />}
              {c.measured && <span className="golf-gap-avg" style={{ left: at(c.measured.average) }} />}
            </span>
            <span className="golf-gap-value">{c.measured ? `${c.measured.average} m` : `${c.carry_m} m`}
              {c.measured && c.carry_m ? <span className="muted small"> ({c.carry_m})</span> : null}</span>
          </li>
        ))}
      </ul>
      <p className="muted small">Bar: the carry you gave it. Band and line: the middle half of your measured shots and their average (from shots
        you marked on the course with that club, to where the next one was played from).</p>
    </>
  )
}

export function ClubPanel({ id = null, club = null, onClose }) {
  const { changed, showToast } = useApp()
  const lists = useGolfLists()
  const [c, setC] = useState(club)
  useEffect(() => {
    if (id != null && !club) api.golfClubs().then((all) => setC(all.find((x) => x.club_id === id) ?? null)).catch((e) => showToast(e.message))
  }, [id, club, showToast])
  if (!lists || (id != null && !c)) return <Drawer title="Club" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const fields = [
    { name: 'name', label: 'Name', required: true, placeholder: 'e.g. 7 iron' },
    { name: 'kind', label: 'Kind', type: 'select', options: lists.club_kinds, required: true },
    { name: 'loft', label: 'Loft (°)', type: 'number', step: 0.5 },
    { name: 'carry_m', label: 'Your carry (m)', type: 'number', hint: 'How far it flies with a good strike (not counting the roll)' },
    { name: 'brand', label: 'Make and model' },
    { name: 'in_bag', label: 'In the bag', type: 'select', options: [['true', 'Yes'], ['false', 'No (kept at home)']], required: true },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  const m = c?.measured
  const before = m ? (
    <Numbers items={[
      { label: 'Measured average', value: `${m.average} m`, sub: plural(m.shots, 'shot') },
      { label: 'Median', value: `${m.median} m` },
      { label: 'Longest', value: `${m.longest} m` },
      { label: 'Usual range', value: `${m.short}–${m.long} m` },
    ]} />
  ) : null
  return (
    <FormPanel title={c ? c.name : 'Add a club'} fields={fields} record={c} defaults={{ kind: 'Iron', in_bag: 'true' }} before={before}
      onClose={onClose} saveLabel={c ? 'Save' : 'Add'}
      onSave={async (data) => {
        const body = { ...data, in_bag: data.in_bag === 'true' }
        if (c) await api.updateGolfClub(c.club_id, body)
        else await api.addGolfClub(Object.fromEntries(Object.entries(body).filter(([, v]) => v != null)))
        changed()
        onClose()
      }}
      onDelete={c && (async () => { await api.deleteGolfClub(c.club_id); changed(); onClose() })} deleteLabel="Remove" />
  )
}

// ---------------------------------------------------------------- practice

export function PracticeView() {
  const { refreshKey, openPanel } = useApp()
  const [p, setP] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.golfPractice().then(setP).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!p) return <p className="muted loading">Loading...</p>
  const year = new Date().getFullYear()
  return (
    <section className="page golf">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('golfpractice', {})}>+ Log practice</button>
      </div>
      {p.sessions.length === 0 ? (
        <EmptyState Icon={TargetIcon} title="No practice yet" action="+ Log practice" onAction={() => openPanel('golfpractice', {})}>
          The range, the putting green, a lesson: what you worked on, for how long - and a drill's score (e.g. 7 of 10 putts from 2 m)
          to see it improve.</EmptyState>
      ) : (
        <>
          <section className="card home-card">
            <h2 className="home-card-title">This year</h2>
            <Numbers items={[
              { label: `Sessions in ${year}`, value: p.year.sessions },
              { label: 'Time', value: p.year.minutes >= 120 ? `${Math.round(p.year.minutes / 6) / 10} h` : `${p.year.minutes} min` },
              { label: 'Balls hit', value: p.year.balls.toLocaleString() },
            ]} />
          </section>
          <div className="home-grid">
            <div className="home-stack">
              <section className="card home-card">
                <h2 className="home-card-title">Sessions</h2>
                <ul className="list plain-list">
                  {p.sessions.map((s) => (
                    <li key={s.practice_id}>
                      <button type="button" className="row-button" onClick={() => openPanel('golfpractice', { id: s.practice_id, session: s })}>
                        <span className="stat-icon low" aria-hidden="true"><TargetIcon size={18} /></span>
                        <span className="grow">
                          <span className="item-title">{shortDate(s.practiced_on)} · {s.kind}</span>
                          <span className="item-meta">{[s.minutes && `${s.minutes} min`, s.balls && `${s.balls} balls`, s.focus,
                            s.drill && `${s.drill}${s.made != null && s.attempts ? `: ${s.made}/${s.attempts}` : ''}`].filter(Boolean).join(' · ')}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
            <div className="home-stack">
              {p.kinds.length > 0 && (
                <section className="card home-card">
                  <h2 className="home-card-title">Minutes by kind (90 days)</h2>
                  <BarList title="Practice minutes by kind, last 90 days" valueLabel="minutes"
                    rows={p.kinds.map((k) => ({ label: k.kind, value: k.minutes, text: `${k.minutes} min · ${plural(k.sessions, 'session')}` }))} />
                </section>
              )}
              {p.drills.length > 0 && (
                <section className="card home-card">
                  <h2 className="home-card-title">Drills</h2>
                  <div className="golf-table-wrap" tabIndex={0} role="region" aria-label="Drills (scrolls sideways)">
                    <table className="golf-table">
                      <thead><tr><th scope="col">Drill</th><th scope="col">Times</th><th scope="col">Best</th><th scope="col">Last</th></tr></thead>
                      <tbody>
                        {p.drills.map((d) => (
                          <tr key={d.drill}>
                            <th scope="row">{d.drill}</th><td>{d.times}</td><td>{d.best_pct}%</td>
                            <td className={d.last_pct >= d.best_pct ? 'golf-sc-under' : undefined}>{d.last} ({d.last_pct}%)</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  )
}

export function PracticePanel({ id = null, session = null, day = null, onClose }) {
  const { changed, showToast } = useApp()
  const lists = useGolfLists()
  const [s, setS] = useState(session)
  const [drills, setDrills] = useState([])
  useEffect(() => {
    api.golfPractice().then((all) => {
      setDrills(all.drills.map((d) => d.drill))
      if (id != null && !session) setS(all.sessions.find((x) => x.practice_id === id) ?? null)
    }).catch((e) => showToast(e.message))
  }, [id, session, showToast])
  if (!lists || (id != null && !s)) return <Drawer title="Practice" onClose={onClose}><p className="muted">Loading...</p></Drawer>
  const fields = [
    { name: 'practiced_on', label: 'Date', type: 'date', required: true },
    { name: 'kind', label: 'Kind', type: 'select', options: lists.practice_kinds, required: true },
    { name: 'minutes', label: 'Minutes', type: 'number', min: 1 },
    { name: 'balls', label: 'Balls', type: 'number', min: 1 },
    { name: 'focus', label: 'Worked on', placeholder: 'e.g. Tempo, 50 m wedges', wide: true },
    { name: 'drill', label: 'Drill', placeholder: 'e.g. Ladder (2 m putts)', list: 'golf-drills' },
    { name: 'made', label: 'Made', type: 'number' },
    { name: 'attempts', label: 'Out of', type: 'number', min: 1 },
    { name: 'notes', label: 'Notes', type: 'textarea' },
  ]
  return (
    <FormPanel title={s ? `${s.kind} practice` : 'Log practice'} fields={fields} record={s} defaults={{ practiced_on: day ?? today(), kind: 'Range' }}
      before={<datalist id="golf-drills">{drills.map((d) => <option key={d} value={d} />)}</datalist>}
      onClose={onClose} saveLabel={s ? 'Save' : 'Log it'}
      onSave={async (data) => {
        if (data.made != null && !data.attempts) throw new Error('A drill\'s score needs "Out of" too.')
        if (s) await api.updateGolfPractice(s.practice_id, data)
        else await api.addGolfPractice(Object.fromEntries(Object.entries(data).filter(([, v]) => v != null)))
        changed()
        onClose()
      }}
      onDelete={s && (async () => { await api.deleteGolfPractice(s.practice_id); changed(); onClose() })} deleteLabel="Remove" />
  )
}
