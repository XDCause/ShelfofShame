import { useEffect, useRef, useState } from 'react'
import { api, today } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// The live board: big HIT / MISS buttons for the range, counting as you go, then "Finish group" wraps it up.
// Each tap is saved as it happens (in order, one at a time), so nothing's lost if the phone sleeps; Undo takes
// back the last. Keys on a computer: H hit, M miss, Backspace undo.

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

const tally = (calls) => {
  const hits = calls.filter(Boolean).length
  let best = 0
  let run = 0
  for (const c of calls) { run = c ? run + 1 : 0; best = Math.max(best, run) }
  return { shots: calls.length, hits, misses: calls.length - hits, rate: calls.length ? Math.round((100 * hits) / calls.length) : null,
    streak: run, best }
}

export default function LiveBoard({ s, lists, onSession, onClose }) {
  const { showToast, changed } = useApp()
  const last = s.groups_list.at(-1)
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
  const start = async () => {
    setBusy(true)
    try {
      const session = await api.addShootingGroup(s.session_id, { distance: Number(setup.distance), unit: setup.unit,
        target: setup.target.trim() || null, position: setup.position || null })
      const g = session.groups_list.at(-1)
      groupId.current = g.group_id
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
  const call = (hit) => {
    setCalls((c) => [...c, hit])
    navigator.vibrate?.(hit ? 25 : [15, 40, 15])
    enqueue(async () => keep(await api.addShot(groupId.current, { hit })))
  }
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
    if (e.key === 'h' || e.key === 'H') call(true)
    else if (e.key === 'm' || e.key === 'M') call(false)
    else if (e.key === 'Backspace' && calls.length) undo()
  }
  const t = tally(calls)
  const set = (k) => (e) => setSetup((x) => ({ ...x, [k]: e.target.value }))
  const label = `${setup.distance} ${setup.unit}${setup.target.trim() ? ` · ${setup.target.trim()}` : ''}`

  return (
    <div className="shoot-board" role="dialog" aria-modal="true" aria-label="Live board" tabIndex={-1} ref={box} onKeyDown={keys}>
      <div className="shoot-board-top">
        <strong>{phase === 'setup' ? 'Live board' : `Group ${groupNo} · ${label}`}</strong>
        <button type="button" className="plain" onClick={phase === 'live' ? finish : onClose}>{phase === 'live' ? 'Finish group' : 'Close'}</button>
      </div>

      {phase === 'setup' && (
        <form className="shoot-board-setup" onSubmit={(e) => { e.preventDefault(); start() }}>
          <p className="muted">Tap HIT or MISS after every shot - it counts as you go.</p>
          <div className="shoot-form-grid">
            <div className="field">Distance<span className="shoot-dist">
              <input type="number" min="1" max="5000" required value={setup.distance} onChange={set('distance')} aria-label="Distance" />
              <select value={setup.unit} onChange={set('unit')} aria-label="Unit"><option value="m">m</option><option value="yd">yd</option></select>
            </span></div>
            <label className="field">Target<input value={setup.target} onChange={set('target')} placeholder="e.g. 2 MOA steel" /></label>
            <label className="field">Position<select value={setup.position} onChange={set('position')}><option value="">—</option>
              {(lists?.positions ?? []).map((p) => <option key={p}>{p}</option>)}</select></label>
          </div>
          <button type="submit" className="primary shoot-board-go" disabled={busy}>Start</button>
        </form>
      )}

      {phase === 'live' && (
        <>
          <div className="shoot-board-counts" aria-live="polite">
            <div><span>{t.shots}</span>shots</div>
            <div className="hit"><span>{t.hits}</span>hits</div>
            <div className="miss"><span>{t.misses}</span>misses</div>
            <div><span>{t.rate == null ? '–' : `${t.rate}%`}</span>hit rate</div>
          </div>
          <p className="shoot-board-streak">{t.streak > 1 ? `${t.streak} in a row` : ' '}{t.best > 1 && <span className="muted"> · best {t.best}</span>}</p>
          <ol className="shoot-board-dots" aria-label="Shots so far">
            {calls.map((c, i) => <li key={i} className={c ? 'hit' : 'miss'} title={`Shot ${i + 1}: ${c ? 'hit' : 'miss'}`}>{i + 1}</li>)}
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

      {phase === 'done' && (
        <div className="shoot-board-done">
          <p className="shoot-board-result">{t.hits}/{t.shots} <span>hits ({t.rate}%)</span></p>
          <p className="muted">Group {groupNo} · {label}{t.best > 1 ? ` · best streak ${t.best}` : ''}</p>
          <ol className="shoot-board-dots">{calls.map((c, i) => <li key={i} className={c ? 'hit' : 'miss'}>{i + 1}</li>)}</ol>
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
