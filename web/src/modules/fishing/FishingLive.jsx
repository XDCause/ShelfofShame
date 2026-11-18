import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import PhotoPick from '../../components/PhotoPick.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'
import { DayCard } from './FishingForecast.jsx'
import { CACHE_KEY, QUEUE_KEY, RECENT_KEY, TRIP_KEY, addLocalCatch, applySwaps, blobToDataUrl, bumpRecent, catchCount, drop, elapsedText,
  enqueue, keep, lengthFrom, load, nearestSpot, newKey, recentFirst, runQueue, sendItem, startLocalTrip } from './fishQueue.js'

// Fishing > Go fishing (/fishing/live): the page for the water, on the phone. Start a trip (a spot - "here" finds the one
// within 2 km or names a new one - how you're fishing and what you're after), then log a catch in three taps (species,
// length, kept or released) with the time and GPS, add a photo, end the trip. It works with NO signal: every write goes into
// a waiting list kept on the phone (fishQueue.js) and is sent in order - at once, when the phone is back online, every
// 20 s and when the page opens - with temporary ids swapped for the server's as they answer. Today's solunar / tide
// periods come from the forecast when there is signal. The pickers (spots, species, lures) are kept from the last visit.
const PLATFORMS = [['shore', 'Shore'], ['jetty', 'Jetty'], ['boat', 'Boat'], ['kayak', 'Kayak'], ['wading', 'Wading']]
const QUICK_LENGTHS = [25, 30, 35, 40, 45, 50, 60, 80]
const SPECIES_SHOWN = 12

const hereNow = () => new Promise((resolve) => {
  if (!navigator.geolocation) { resolve(null); return }
  navigator.geolocation.getCurrentPosition(
    (p) => resolve({ lat: Number(p.coords.latitude.toFixed(6)), lon: Number(p.coords.longitude.toFixed(6)) }),
    () => resolve(null),
    { enableHighAccuracy: true, timeout: 6000, maximumAge: 120000 })
})

// ---------------------------------------------------------------- the trip and its waiting list

function useLiveTrip(showToast) {
  const [trip, setTripState] = useState(() => load(TRIP_KEY))
  const [queue, setQueueState] = useState(() => load(QUEUE_KEY) ?? [])
  const [stalled, setStalled] = useState(false)
  const tripRef = useRef(trip)
  const qRef = useRef(queue)
  const running = useRef(null)
  const setTrip = useCallback((t) => {
    tripRef.current = t
    setTripState(t)
    if (t) keep(TRIP_KEY, t)
    else drop(TRIP_KEY)
  }, [])
  const setQ = useCallback((q) => {
    qRef.current = q
    setQueueState(q)
    if (q.length) keep(QUEUE_KEY, q)
    else drop(QUEUE_KEY)
  }, [])
  const push = useCallback((item) => setQ(enqueue(qRef.current, item)), [setQ])

  // Send what's waiting (one run at a time: a second call waits for the first).
  const flush = useCallback(() => {
    if (running.current) return running.current
    running.current = (async () => {
      const store = {
        get: () => qRef.current,
        set: setQ,
        swapped: (s) => { if (tripRef.current) setTrip(applySwaps(tripRef.current, [s])) },
      }
      const out = await runQueue(store, (item, wasTried) => sendItem(api, item, wasTried))
      for (const { item, result } of out.results) {
        const warnings = item.kind === 'catch' ? (result?.warnings ?? result?.catch?.warnings ?? []) : []
        const t = tripRef.current
        if (warnings.length && t) setTrip({ ...t, catches: t.catches.map((c) => (c.key === item.temp ? { ...c, warnings } : c)) })
      }
      for (const { item, error } of out.dropped) showToast(`A ${item.kind === 'photo' ? 'photo' : item.kind === 'catch' ? 'catch' : 'change'} wasn't saved: ${error.message}`)
      setStalled(out.stalled)
    })().finally(() => { running.current = null })
    return running.current
  }, [setQ, setTrip, showToast])

  return { trip, queue, stalled, tripRef, qRef, setTrip, push, flush }
}

// ---------------------------------------------------------------- the pickers' lists (kept for no signal)

function useLists() {
  const [lists, setLists] = useState(() => load(CACHE_KEY) ?? { spots: [], species: [], lures: [] })
  useEffect(() => {
    let gone = false
    Promise.allSettled([api.fishingLiveSpots(), api.fishingLiveSpecies(), api.fishingLiveLures()]).then((r) => {
      if (gone) return
      const [spots, species, lures] = r.map((x) => (x.status === 'fulfilled' && Array.isArray(x.value) ? x.value : null))
      setLists((was) => {
        const next = { spots: spots ?? was.spots, species: species ?? was.species, lures: lures ?? was.lures }
        if (spots || species || lures) keep(CACHE_KEY, next)
        return next
      })
    })
    return () => { gone = true }
  }, [])
  return lists
}

// ---------------------------------------------------------------- start

function StartForm({ spots, onStart }) {
  const [spotId, setSpotId] = useState('')
  const [here, setHere] = useState(null)               // {lat, lon} from "Use my position"
  const [name, setName] = useState('')                  // a new spot's name
  const [note, setNote] = useState('')
  const [looking, setLooking] = useState(false)
  const [platform, setPlatform] = useState('')
  const [target, setTarget] = useState('')
  const useHere = async () => {
    setLooking(true)
    setNote('')
    const p = await hereNow()
    setLooking(false)
    if (!p) { setNote("Couldn't find where you are (location allowed? a clear sky helps). Pick a spot or start without one."); return }
    setHere(p)
    const near = nearestSpot(spots, p, 2000)
    if (near) { setSpotId(String(near.spot.spot_id)); setName(''); setNote(`${near.spot.name}, ${Math.round(near.metres)} m away.`) }
    else { setSpotId(''); setNote('No spot of yours within 2 km: name this one to keep it.') }
  }
  const newSpot = here && !spotId
  const go = () => {
    const spot = spots.find((s) => String(s.spot_id) === spotId)
    onStart({
      spot, platform: platform || null, target: target.trim() || null,
      newSpot: newSpot && name.trim() ? { name: name.trim(), lat: here.lat, lon: here.lon } : null,
    })
  }
  return (
    <section className="card fstl-start">
      <h2 className="home-card-title">Go fishing</h2>
      <label className="field">Where
        <select value={spotId} onChange={(e) => { setSpotId(e.target.value); setNote('') }}>
          <option value="">No spot / not sure</option>
          {spots.map((s) => <option key={s.spot_id} value={s.spot_id}>{s.name}</option>)}
        </select></label>
      <button type="button" className="secondary fstl-big" onClick={useHere} disabled={looking}>{looking ? 'Finding you...' : 'Use my position'}</button>
      {note && <p className="muted small" role="status">{note}</p>}
      {newSpot && (
        <label className="field">Name this spot
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Wynnum jetty" /></label>)}
      <div className="field" role="group" aria-label="How you're fishing">
        <span>How</span>
        <div className="fstl-chips">
          {PLATFORMS.map(([id, label]) => (
            <button key={id} type="button" className="secondary fstl-chip" aria-pressed={platform === id} onClick={() => setPlatform(platform === id ? '' : id)}>{label}</button>))}
        </div>
      </div>
      <label className="field">After
        <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Flathead, bream... (optional)" /></label>
      <button type="button" className="primary fstl-big" onClick={go}>Start fishing</button>
    </section>
  )
}

// ---------------------------------------------------------------- log a catch

function CatchSheet({ species, lures, recent, onSave, onCancel }) {
  const [pick, setPick] = useState(null)               // {id} or {name} (typed)
  const [filter, setFilter] = useState('')
  const [all, setAll] = useState(false)
  const [length, setLength] = useState('')
  const [lure, setLure] = useState(() => (lures.some((l) => l.lure_id === recent.lure) ? String(recent.lure) : ''))
  const [busy, setBusy] = useState(false)
  const ordered = recentFirst(species, recent.species, 'species_id')
  const f = filter.trim().toLowerCase()
  const matches = ordered.filter((s) => s.name.toLowerCase().includes(f))
  const shown = f || all ? matches : matches.slice(0, SPECIES_SHOWN)
  const exact = ordered.some((s) => s.name.toLowerCase() === f)
  const n = lengthFrom(length)
  const step = (d) => setLength(String(Math.max(1, Math.round(((n ?? 30) + d) * 10) / 10)))
  const save = async (fate) => {
    setBusy(true)
    await onSave({ pick, length: n, fate, lure: lure ? Number(lure) : null })
    setBusy(false)
  }
  const chosen = pick?.id ? species.find((s) => s.species_id === pick.id)?.name : pick?.name
  return (
    <section className="card fstl-sheet" aria-label="Log a catch">
      <h2 className="home-card-title">What did you catch?</h2>
      <input type="search" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Find or type a species" aria-label="Find or type a species" />
      <div className="fstl-chips">
        {shown.map((s) => (
          <button key={s.species_id} type="button" className="secondary fstl-chip" aria-pressed={pick?.id === s.species_id}
            onClick={() => setPick({ id: s.species_id })}>{s.name}</button>))}
        {f && !exact && (
          <button type="button" className="secondary fstl-chip" aria-pressed={pick?.name === filter.trim()} onClick={() => setPick({ name: filter.trim() })}>
            Use &quot;{filter.trim()}&quot;</button>)}
        {!f && !all && matches.length > SPECIES_SHOWN && (
          <button type="button" className="plain fstl-chip" onClick={() => setAll(true)}>More...</button>)}
      </div>
      {chosen && <p className="fstl-chosen"><strong>{chosen}</strong></p>}
      <div className="field">
        <span>Length (cm)</span>
        <span className="fstl-length">
          <button type="button" className="secondary fstl-step" onClick={() => step(-1)} aria-label="1 cm shorter">-</button>
          <input inputMode="decimal" value={length} onChange={(e) => setLength(e.target.value)} placeholder="not measured" aria-label="Length (cm)" />
          <button type="button" className="secondary fstl-step" onClick={() => step(1)} aria-label="1 cm longer">+</button>
        </span></div>
      <div className="fstl-chips" aria-label="Quick lengths">
        {QUICK_LENGTHS.map((q) => (
          <button key={q} type="button" className="plain fstl-chip" aria-pressed={n === q} onClick={() => setLength(String(q))}>{q}</button>))}
      </div>
      {lures.length > 0 && (
        <label className="field">On
          <select value={lure} onChange={(e) => setLure(e.target.value)}>
            <option value="">Nothing noted</option>
            {recentFirst(lures, recent.lures, 'lure_id').map((l) => <option key={l.lure_id} value={l.lure_id}>{l.name}</option>)}
          </select></label>)}
      <div className="fstl-fates">
        <button type="button" className="primary fstl-big" disabled={!pick || busy} onClick={() => save('kept')}>Kept</button>
        <button type="button" className="primary fstl-big" disabled={!pick || busy} onClick={() => save('released')}>Released</button>
      </div>
      <div className="fstl-fates">
        <button type="button" className="secondary" disabled={!pick || busy} onClick={() => save('tagged')}>Tagged</button>
        <button type="button" className="secondary" disabled={!pick || busy} onClick={() => save('died')}>Died</button>
        <button type="button" className="plain" onClick={onCancel}>Cancel</button>
      </div>
    </section>
  )
}

// ---------------------------------------------------------------- the trip on the water

function TodayStrip({ trip }) {
  const [day, setDay] = useState(null)
  const [state, setState] = useState('loading')
  const spotId = typeof trip.spot_id === 'number' ? trip.spot_id : null
  useEffect(() => {
    let gone = false
    if (spotId == null) { setState('none'); return undefined }
    api.fishingForecast({ spot_id: spotId }).then((r) => {
      if (gone) return
      setDay(r?.days?.[0] ?? null)
      setState(r?.days?.[0] ? 'ok' : 'none')
    }).catch(() => { if (!gone) setState('offline') })
    return () => { gone = true }
  }, [spotId])
  if (state === 'ok') return <ul className="fstl-today"><DayCard day={day} compact /></ul>
  if (state === 'offline') return <p className="muted small">Today&apos;s moon and tide periods show when there is signal.</p>
  return null
}

function CatchRow({ c, open, onPhoto }) {
  const [busy, setBusy] = useState(false)
  const [showPick, setShowPick] = useState(open)
  const add = async (file) => {
    setBusy(true)
    await onPhoto(c, file)
    setBusy(false)
    setShowPick(false)
  }
  return (
    <li className="fstl-catch">
      <div className="fstl-catch-head">
        <strong>{c.species}</strong>
        <span>{c.length ? `${c.length} cm` : ''}</span>
        <span className="badge">{c.fate}</span>
        <span className="muted small">{new Date(c.at).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}</span>
      </div>
      {(c.warnings ?? []).map((w) => <p key={w} className="alert low small" role="alert">{w}</p>)}
      {c.photos > 0 && <p className="muted small">{c.photos} {c.photos === 1 ? 'photo' : 'photos'} added</p>}
      {showPick ? (busy ? <span className="muted small">Saving...</span> : <PhotoPick onFile={add} label="Add photo" />)
        : <button type="button" className="plain small" onClick={() => setShowPick(true)}>Add a photo</button>}
    </li>
  )
}

function TripScreen({ live, lists, recent, setRecent, onEnd }) {
  const { trip, queue, stalled, setTrip, push, flush } = live
  const [now, setNow] = useState(() => Date.now())
  const [logging, setLogging] = useState(false)
  const [ending, setEnding] = useState(false)
  const [lastKey, setLastKey] = useState(null)
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 20000)
    return () => clearInterval(t)
  }, [])

  const saveCatch = async ({ pick, length, fate, lure }) => {
    const here = await hereNow()
    const key = newKey('c')
    const sp = pick.id ? lists.species.find((s) => s.species_id === pick.id) : null
    const at = new Date().toISOString()
    const data = {
      ...(pick.id ? { species_id: pick.id } : { species: pick.name }),
      fate, caught_at: at,
      ...(length != null ? { length_cm: length } : {}),
      ...(lure != null ? { lure_id: lure } : {}),
      ...(here ?? {}),
    }
    push({ kind: 'catch', temp: key, trip: live.tripRef.current.id, data })
    setTrip(addLocalCatch(live.tripRef.current, { key, id: key, species: sp?.name ?? pick.name, length, fate, at, warnings: [], photos: 0 }))
    setRecent({ species: bumpRecent(recent.species, pick.id ?? pick.name), lures: lure != null ? bumpRecent(recent.lures, lure) : recent.lures, lure: lure ?? recent.lure })
    setLastKey(key)
    setLogging(false)
    flush()
  }
  const addPhoto = async (c, file) => {
    const dataUrl = await blobToDataUrl(await shrink(file, 1600))
    push({ kind: 'photo', catch: live.tripRef.current.catches.find((x) => x.key === c.key)?.id ?? c.id, dataUrl })
    setTrip({ ...live.tripRef.current, catches: live.tripRef.current.catches.map((x) => (x.key === c.key ? { ...x, photos: (x.photos ?? 0) + 1 } : x)) })
    flush()
  }
  const end = () => {
    push({ kind: 'end', trip: live.tripRef.current.id, data: { ended_at: new Date().toISOString() } })
    const done = live.tripRef.current
    setTrip(null)
    flush()
    onEnd(done)
  }
  if (logging) {
    return <CatchSheet species={lists.species} lures={lists.lures} recent={recent} onSave={saveCatch} onCancel={() => setLogging(false)} />
  }
  return (
    <section className="fstl-trip">
      <div className="card fstl-status">
        <h2 className="home-card-title">{trip.spot_name || 'Fishing'}</h2>
        <p className="fstl-timer" aria-label="Time fishing">{elapsedText(trip.started_at, now)}</p>
        <p className="muted small">{[trip.platform, trip.target].filter(Boolean).join(' · ')}</p>
        <p><strong className="fstl-count">{catchCount(trip)}</strong> fish so far</p>
        {queue.length > 0 && (
          <p className="badge low fstl-waiting" role="status">
            {queue.length} waiting to send{stalled ? ' (no signal)' : ''}{' '}
            <button type="button" className="plain small" onClick={() => flush()}>Send now</button></p>)}
      </div>
      <button type="button" className="primary fstl-fish" onClick={() => setLogging(true)}>Fish!</button>
      <TodayStrip trip={trip} />
      {trip.catches.length > 0 && (
        <ul className="fstl-catches" aria-label="This trip's catches">
          {[...trip.catches].reverse().map((c) => <CatchRow key={c.key} c={c} open={c.key === lastKey && !c.photos} onPhoto={addPhoto} />)}
        </ul>)}
      {ending ? (
        <div className="card fstl-endask">
          <p>End this trip now?</p>
          <button type="button" className="primary" onClick={end}>End trip</button>{' '}
          <button type="button" className="secondary" onClick={() => setEnding(false)}>Keep fishing</button>
        </div>
      ) : <button type="button" className="secondary fstl-big" onClick={() => setEnding(true)}>End trip</button>}
    </section>
  )
}

// ---------------------------------------------------------------- the page

export function LiveView() {
  const { showToast } = useApp()
  const live = useLiveTrip(showToast)
  const { trip, queue, stalled, setTrip, push, flush } = live
  const lists = useLists()
  const [recent, setRecentState] = useState(() => load(RECENT_KEY) ?? { species: [], lures: [], lure: null })
  const [done, setDone] = useState(null)               // the trip just ended
  const [ready, setReady] = useState(false)
  const setRecent = (r) => { setRecentState(r); keep(RECENT_KEY, r) }

  // On opening: send what's waiting, then (with no trip kept here) carry on one that's open on the server
  useEffect(() => {
    let gone = false
    ;(async () => {
      await flush()
      if (!gone && !live.tripRef.current && live.qRef.current.length === 0) {
        try {
          const open = (await api.fishingLiveSummary())?.open_trip
          if (open && !gone && !live.tripRef.current) {
            setTrip(startLocalTrip({ id: open.trip_id, started_at: open.started_at, spot_id: open.spot_id, spot_name: open.spot_name ?? '',
              platform: open.platform, target: open.target ?? '', base: open.catches ?? 0 }))
          }
        } catch { /* no signal: start a new one, or wait */ }
      }
      if (!gone) setReady(true)
    })()
    return () => { gone = true }
  }, [flush, setTrip, live.tripRef, live.qRef])

  // Back online, every 20 s and when the phone comes back to this page: send what's waiting
  useEffect(() => {
    const go = () => { if (live.qRef.current.length) flush() }
    const visible = () => { if (document.visibilityState === 'visible') go() }
    window.addEventListener('online', go)
    document.addEventListener('visibilitychange', visible)
    const timer = setInterval(go, 20000)
    return () => { window.removeEventListener('online', go); document.removeEventListener('visibilitychange', visible); clearInterval(timer) }
  }, [flush, live.qRef])

  const start = ({ spot, platform, target, newSpot }) => {
    const tmp = newKey('t')
    let spotRef = spot ? spot.spot_id : null
    let spotName = spot?.name ?? ''
    if (newSpot) {
      spotRef = newKey('s')
      spotName = newSpot.name
      push({ kind: 'spot', temp: spotRef, data: newSpot })
    }
    const started_at = new Date().toISOString()
    push({ kind: 'trip', temp: tmp, spot: spotRef, data: { started_at, platform, target } })
    setTrip(startLocalTrip({ id: tmp, started_at, spot_id: spotRef, spot_name: spotName, platform, target: target ?? '' }))
    setDone(null)
    flush()
  }

  if (!ready && !trip) return <p className="muted loading">Looking for your trip...</p>
  return (
    <section className="page fstl-live">
      {trip ? (
        <TripScreen live={live} lists={lists} recent={recent} setRecent={setRecent} onEnd={setDone} />
      ) : (
        <>
          {done && (
            <div className="card fstl-done" role="status">
              <h2 className="home-card-title">Trip ended</h2>
              <p>{catchCount(done)} fish in {elapsedText(done.started_at, Date.now())}.
                {queue.length > 0 ? ` ${queue.length} waiting to send${stalled ? ' (no signal)' : ''}.` : ' Everything is saved.'}</p>
              <Link className="button secondary" to="/fishing/dashboard">Back to Fishing</Link>
            </div>)}
          {queue.length > 0 && !done && (
            <p className="badge low fstl-waiting" role="status">{queue.length} waiting to send{stalled ? ' (no signal)' : ''}{' '}
              <button type="button" className="plain small" onClick={() => flush()}>Send now</button></p>)}
          <StartForm spots={lists.spots} onStart={start} />
        </>
      )}
    </section>
  )
}
