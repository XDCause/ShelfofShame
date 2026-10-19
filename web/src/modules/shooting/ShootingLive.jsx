import { useEffect, useRef, useState } from 'react'
import { api, today } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { ShotPlot } from './ShootingShots.jsx'
import { correction, groupStats, toAngle } from './shootingParts.jsx'

// The live board, for the range. Two ways to shoot a group:
//   Hit / miss  big HIT and MISS buttons (steel, gongs, a scoring zone) - shots, hits, hit rate, streak
//   Target      a target face: tap where each shot landed - the group's size, mean radius and what to dial,
//               worked out with every shot; "Off target" for one that missed the paper
// Either way it counts as you go, every tap is saved as it happens (in order, one at a time - nothing's lost if
// the phone sleeps), Undo takes back the last, and "Finish group" wraps it up. Keys on a computer: H hit, M miss
// (or off target), Backspace undo.

const MODE_KEY = 'offtheclock.shooting.boardMode'       // which way you shot last, on this device
const savedMode = () => { try { return localStorage.getItem(MODE_KEY) === 'target' ? 'target' : 'hits' } catch { return 'hits' } }
const saveMode = (m) => { try { localStorage.setItem(MODE_KEY, m) } catch { /* private window */ } }

// Start shooting now: today's session if there is one, else a new one with what you used last (or your club).
export async function startShooting(app) {
  const [last] = await api.shootingSessions()
  if (last && last.shot_on === today()) {
    app.openPanel('shootsession', { id: last.session_id, live: true })
    return
  }
  const club = last ? null : (await api.shootingRanges()).find((r) => r.counts_for_club)
  const s = await api.addShootingSession({ shot_on: today(), kind: 'Practice', range_id: last?.range_id ?? club?.range_id ?? null,
    rifle_id: last?.rifle_id ?? null, ammo_id: last?.ammo_id ?? null })
  app.changed()
  app.openPanel('shootsession', { id: s.session_id, live: true })
}

// calls: [{hit: true | false | null, x_mm?, y_mm?}] in the order fired
const tally = (calls) => {
  const hits = calls.filter((c) => c.hit === true).length
  const misses = calls.filter((c) => c.hit === false).length
  let best = 0
  let run = 0
  for (const c of calls) { run = c.hit === false ? 0 : run + 1; best = Math.max(best, run) }
  return { shots: calls.length, hits, misses, rate: hits + misses ? Math.round((100 * hits) / (hits + misses)) : null, streak: run, best }
}

export default function LiveBoard({ s, lists, onSession, onClose }) {
  const { showToast, changed } = useApp()
  const last = s.groups_list.at(-1)
  const [mode, setMode] = useState(savedMode)
  const [setup, setSetup] = useState({ distance: String(last?.distance ?? 100), unit: last?.unit ?? 'm', target: last?.target ?? '',
    position: last?.position ?? '' })
  const [phase, setPhase] = useState('setup')        // setup -> live -> done
  const [calls, setCalls] = useState([])
  const [groupNo, setGroupNo] = useState(s.groups_list.length)
  const [busy, setBusy] = useState(false)
  const groupId = useRef(null)
  const ids = useRef([])                  // the saved shots' ids, in order (for Undo)
  const latest = useRef(s)
  const queue = useRef(Promise.resolve())
  const box = useRef(null)
  useEffect(() => { box.current?.focus() }, [phase])

  const enqueue = (fn) => {
    queue.current = queue.current.then(fn).catch((e) => showToast(e.message))
    return queue.current
  }
  const keep = (session) => {
    latest.current = session
    ids.current = session.groups_list.find((g) => g.group_id === groupId.current)?.shot_list.map((x) => x.shot_id) ?? []
  }
  const pickMode = (m) => { setMode(m); saveMode(m) }
  const start = async () => {
    setBusy(true)
    try {
      const session = await api.addShootingGroup(s.session_id, { distance: Number(setup.distance), unit: setup.unit,
        target: setup.target.trim() || null, position: setup.position || null })
      groupId.current = session.groups_list.at(-1).group_id
      ids.current = []
      latest.current = session
      setGroupNo(session.groups_list.length)
      setCalls([])
      setPhase('live')
      onSession(session)
    } catch (e) {
      showToast(e.message)
    } finally {
      setBusy(false)
    }
  }
  const record = (shot) => {
    setCalls((c) => [...c, shot])
    navigator.vibrate?.(shot.hit === false ? [15, 40, 15] : 25)
    enqueue(async () => keep(await api.addShot(groupId.current, shot)))
  }
  const call = (hit) => record({ hit })
  const placed = (x, y) => record({ hit: null, x_mm: x, y_mm: y })
  const undo = () => {
    setCalls((c) => c.slice(0, -1))
    enqueue(async () => {
      const id = ids.current.at(-1)
      if (id) keep(await api.deleteShot(id))
    })
  }
  const finish = async () => {
    setBusy(true)
    await queue.current
    if (!calls.length && groupId.current) {
      // nothing shot: don't leave an empty group behind
      try { latest.current = await api.deleteShootingGroup(groupId.current) } catch { /* already gone */ }
    }
    onSession(latest.current)
    changed()
    setBusy(false)
    setPhase(calls.length ? 'done' : 'setup')
  }
  const keys = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); if (phase === 'live') finish(); else onClose() }
    if (phase !== 'live' || e.target.tagName === 'INPUT') return
    if ((e.key === 'h' || e.key === 'H') && mode === 'hits') call(true)
    else if (e.key === 'm' || e.key === 'M') call(false)
    else if (e.key === 'Backspace' && calls.length) undo()
  }
  const t = tally(calls)
  const set = (k) => (e) => setSetup((x) => ({ ...x, [k]: e.target.value }))
  const label = `${setup.distance} ${setup.unit}${setup.target.trim() ? ` · ${setup.target.trim()}` : ''}`

  // Target mode: the group as it stands, worked out here so it updates the moment you tap
  const unit = s.scope_unit ?? 'MOA'
  const metres = Number(setup.distance) * (setup.unit === 'yd' ? 0.9144 : 1)
  const onPaper = calls.filter((c) => c.x_mm != null)
  const stats = groupStats(onPaper)
  const plotGroup = {
    distance: setup.distance, unit: setup.unit, metres, scope_unit: unit,
    shot_list: calls.map((c, i) => ({ ...c, shot_id: i + 1, n: i + 1, flyer: false })).filter((c) => c.x_mm != null),
    spread: stats && onPaper.length > 1 ? stats : null,
  }
  const sizeText = stats && onPaper.length > 1 ? `${toAngle(stats.size_mm, metres, unit).toFixed(2)} ${unit}` : '–'
  const mrText = stats && onPaper.length > 1 ? `${toAngle(stats.mean_radius_mm, metres, unit).toFixed(2)} ${unit}` : '–'
  const dial = stats ? correction(stats.up_mm, stats.right_mm, metres, unit, s.click) : null
  const offPaper = calls.filter((c) => c.hit === false).length

  return (
    <div className="shoot-board" role="dialog" aria-modal="true" aria-label="Live board" tabIndex={-1} ref={box} onKeyDown={keys}>
      <div className="shoot-board-top">
        <strong>{phase === 'setup' ? 'Live board' : `Group ${groupNo} · ${label}`}</strong>
        <button type="button" className="plain" onClick={phase === 'live' ? finish : onClose}>{phase === 'live' ? 'Finish group' : 'Close'}</button>
      </div>

      {phase === 'setup' && (
        <form className="shoot-board-setup" onSubmit={(e) => { e.preventDefault(); start() }}>
          <div className="segmented shoot-board-mode" role="group" aria-label="How to count">
            <button type="button" aria-pressed={mode === 'hits'} onClick={() => pickMode('hits')}>Hit / miss</button>
            <button type="button" aria-pressed={mode === 'target'} onClick={() => pickMode('target')}>Target</button>
          </div>
          <p className="muted">{mode === 'hits' ? 'Tap HIT or MISS after every shot - it counts as you go.'
            : `Tap the target where each shot landed - the group, its centre and what to dial work out as you go (${unit}).`}</p>
          <div className="shoot-form-grid">
            <div className="field">Distance<span className="shoot-dist">
              <input type="number" min="1" max="5000" required value={setup.distance} onChange={set('distance')} aria-label="Distance" />
              <select value={setup.unit} onChange={set('unit')} aria-label="Unit"><option value="m">m</option><option value="yd">yd</option></select>
            </span></div>
            <label className="field">Target<input value={setup.target} onChange={set('target')}
              placeholder={mode === 'hits' ? 'e.g. 2 MOA steel' : 'e.g. 50 m smallbore card'} /></label>
            <label className="field">Position<select value={setup.position} onChange={set('position')}><option value="">—</option>
              {(lists?.positions ?? []).map((p) => <option key={p}>{p}</option>)}</select></label>
          </div>
          <button type="submit" className="primary shoot-board-go" disabled={busy}>Start</button>
        </form>
      )}

      {phase === 'live' && mode === 'hits' && (
        <>
          <div className="shoot-board-counts" aria-live="polite">
            <div><span>{t.shots}</span>shots</div>
            <div className="hit"><span>{t.hits}</span>hits</div>
            <div className="miss"><span>{t.misses}</span>misses</div>
            <div><span>{t.rate == null ? '–' : `${t.rate}%`}</span>hit rate</div>
          </div>
          <p className="shoot-board-streak">{t.streak > 1 ? `${t.streak} in a row` : ' '}{t.best > 1 && <span className="muted"> · best {t.best}</span>}</p>
          <ol className="shoot-board-dots" aria-label="Shots so far">
            {calls.map((c, i) => <li key={i} className={c.hit ? 'hit' : 'miss'} title={`Shot ${i + 1}: ${c.hit ? 'hit' : 'miss'}`}>{i + 1}</li>)}
          </ol>
          <div className="shoot-board-buttons">
            <button type="button" className="shoot-board-hit" onClick={() => call(true)}>HIT</button>
            <button type="button" className="shoot-board-miss" onClick={() => call(false)}>MISS</button>
          </div>
          <div className="shoot-board-foot">
            <button type="button" className="secondary" onClick={undo} disabled={!calls.length}>Undo</button>
            <button type="button" className="primary" onClick={finish} disabled={busy}>Finish group</button>
          </div>
        </>
      )}

      {phase === 'live' && mode === 'target' && (
        <>
          <div className="shoot-board-counts" aria-live="polite">
            <div><span>{t.shots}</span>shots</div>
            <div><span className="shoot-board-small">{sizeText}</span>group</div>
            <div><span className="shoot-board-small">{mrText}</span>mean radius</div>
            <div className="miss"><span>{offPaper}</span>off target</div>
          </div>
          <p className="shoot-board-streak">{dial ?? 'Tap where your first shot landed'}</p>
          <ShotPlot g={plotGroup} plotting rings onAdd={placed} className="shoot-board-target" />
          <div className="shoot-board-foot">
            <button type="button" className="secondary" onClick={undo} disabled={!calls.length}>Undo</button>
            <button type="button" className="secondary" onClick={() => call(false)}>Off target</button>
            <button type="button" className="primary" onClick={finish} disabled={busy}>Finish group</button>
          </div>
        </>
      )}

      {phase === 'done' && (
        <div className="shoot-board-done">
          {mode === 'hits' ? <>
            <p className="shoot-board-result">{t.hits}/{t.shots} <span>hits ({t.rate}%)</span></p>
            <p className="muted">Group {groupNo} · {label}{t.best > 1 ? ` · best streak ${t.best}` : ''}</p>
            <ol className="shoot-board-dots">{calls.map((c, i) => <li key={i} className={c.hit ? 'hit' : 'miss'}>{i + 1}</li>)}</ol>
          </> : <>
            <p className="shoot-board-result">{sizeText} <span>{t.shots} shots · mean radius {mrText}</span></p>
            <p className="muted">Group {groupNo} · {label}{offPaper ? ` · ${offPaper} off target` : ''}{dial ? ` · ${dial}` : ''}</p>
            <ShotPlot g={plotGroup} plotting={false} rings className="shoot-board-target small" />
          </>}
          <div className="shoot-board-foot">
            <button type="button" className="primary" onClick={start} disabled={busy}>Next group ({label})</button>
            <button type="button" className="secondary" onClick={() => setPhase('setup')}>Change distance</button>
            <button type="button" className="plain" onClick={onClose}>Done</button>
          </div>
        </div>
      )}
    </div>
  )
}
