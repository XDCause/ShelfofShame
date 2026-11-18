// Fishing's live trip page (FishingLive.jsx) works with no signal: every write (a new spot, the trip start, each catch,
// each photo, the end of the trip) goes into a waiting list kept in localStorage and is sent in order - at once, when the
// phone says it's online again and when the page opens. Like golf's live round (modules/golf/golfMath.js), but things
// made on the phone have no server id yet, so they get a TEMPORARY one ("tmp-...") that later items refer to; when the
// server answers, the real id replaces the temporary one in everything still waiting.
//
// Resending is safe: a catch carries its client_key (the temporary id), and the server answers a key it already has with
// that catch instead of making a second one. A trip start carries its temporary id as client_key too (the server answers a repeat with
// the same trip); a start that may have been sent is still checked against the open trip first (sendItem). A photo whose answer was lost could be saved twice: rare, and deletable.
// Plain helpers, tested in web/src/tests/fishingToolsQueue.test.js.

export const QUEUE_KEY = 'offtheclock.fishing.queue'
export const TRIP_KEY = 'offtheclock.fishing.trip'
export const CACHE_KEY = 'offtheclock.fishing.cache'      // {spots, species, lures}: so the pickers work without signal
export const RECENT_KEY = 'offtheclock.fishing.recent'    // {species: [], lures: [], lure: last lure}

// localStorage can be missing or full (a private window): never let it stop fishing
export const load = (k) => { try { return JSON.parse(localStorage.getItem(k)) } catch { return null } }
export const keep = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* full or blocked: the page works from memory */ } }
export const drop = (k) => { try { localStorage.removeItem(k) } catch { /* blocked */ } }

let counter = 0
export const newKey = (what = 'c') => `tmp-${what}-${Date.now().toString(36)}-${(counter += 1)}-${Math.random().toString(36).slice(2, 6)}`
export const isTemp = (v) => typeof v === 'string' && v.startsWith('tmp-')

// What to do with a failed send: 'retry' (no network, the server's having trouble, or signed out: after signing in again)
// or 'drop' (the server said no: sending it again won't help).
export const failure = (err) => (err?.status == null || err.status >= 500 || [401, 408, 429].includes(err.status) ? 'retry' : 'drop')

// ---------------------------------------------------------------- the waiting list

// An item: {n, kind: 'spot' | 'trip' | 'catch' | 'photo' | 'end', temp?, trip?, spot?, catch?, data?}. `temp` is the
// temporary id this item makes (its answer's real id replaces it in the items after it); trip / spot / catch say which
// (real or temporary) one the item belongs to.
export const enqueue = (queue, item) => [...queue, { ...item, n: newKey('q') }]

export function swapRef(queue, temp, real) {
  const swap = (v) => (v === temp ? real : v)
  return queue.map((q) => ({ ...q, trip: swap(q.trip), spot: swap(q.spot), catch: swap(q.catch) }))
}

const idOf = (item, r) => (item.kind === 'spot' ? r?.spot_id : item.kind === 'trip' ? r?.trip_id : r?.catch_id ?? r?.catch?.catch_id)

// Send what's waiting, in order, one at a time. store = {get(), set(queue), swapped?(swap)}: the list is read afresh for every item, so
// what's added while a send is under way isn't lost (the head is always the item being sent; new ones go on the end).
// send(item, wasTried) does the call. Stops at the first item that should be retried (no signal). Returns what happened.
export async function runQueue(store, send) {
  const out = { swaps: [], results: [], dropped: [], stalled: false }
  const pop = () => store.get().slice(1)
  while (store.get().length) {
    const item = store.get()[0]
    if ([item.trip, item.spot, item.catch].some(isTemp)) {      // what it belongs to never got saved
      out.dropped.push({ item, error: new Error("what it belongs to wasn't saved") })
      store.set(pop())
      continue
    }
    const wasTried = item.tried === true
    if (item.kind === 'trip' && !wasTried) store.set([{ ...item, tried: true }, ...pop()])   // (a start may now have gone out)
    try {
      const result = await send(item, wasTried)
      let rest = pop()
      const real = item.temp ? idOf(item, result) : null
      const swap = real != null ? { temp: item.temp, real, kind: item.kind } : null
      if (swap) { rest = swapRef(rest, swap.temp, swap.real); out.swaps.push(swap) }
      store.set(rest)
      if (swap) store.swapped?.(swap)             // at once, so what's added next already carries the real id
      out.results.push({ item, result })
    } catch (error) {
      if (failure(error) === 'retry') { out.stalled = true; return out }
      store.set(pop())
      out.dropped.push({ item, error })
    }
  }
  return out
}

const sameTime = (a, b) => Math.abs(new Date(a).getTime() - new Date(b).getTime()) < 2000

// The call for an item (api = the api object). A trip start that may already have gone out is first looked for among the
// open trips, so a lost answer doesn't make two trips.
export async function sendItem(api, item, wasTried = false) {
  if (item.kind === 'spot') return api.fishingLiveAddSpot(item.data)
  if (item.kind === 'trip') {
    if (wasTried) {
      const open = (await api.fishingLiveSummary())?.open_trip
      if (open && sameTime(open.started_at, item.data.started_at)) return open
    }
    return api.fishingLiveStart({ ...item.data, spot_id: item.spot ?? null, client_key: item.temp })
  }
  if (item.kind === 'catch') return api.fishingLiveCatch(item.trip, { ...item.data, client_key: item.temp })
  if (item.kind === 'photo') return api.addFishingPhoto(item.catch, dataUrlToBlob(item.dataUrl))
  if (item.kind === 'end') return api.fishingLiveEnd(item.trip, { ended_at: item.data?.ended_at })
  throw Object.assign(new Error(`unknown item ${item.kind}`), { status: 400 })
}

// A photo waits in the list as a data: address (localStorage keeps text); it's about 100-200 KB once shrunk.
export function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = () => reject(r.error)
    r.readAsDataURL(blob)
  })
}
export function dataUrlToBlob(url) {
  const [head, data] = String(url).split(',', 2)
  const type = head.match(/^data:([^;]+);base64$/)?.[1] ?? 'image/jpeg'
  const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0))
  return new Blob([bytes], { type })
}

// ---------------------------------------------------------------- the trip kept on this phone

export const startLocalTrip = ({ id, started_at, spot_id = null, spot_name = '', platform = null, target = '', base = 0 }) =>
  ({ id, started_at, spot_id, spot_name, platform, target, base, catches: [] })

export const addLocalCatch = (trip, c) => ({ ...trip, catches: [...trip.catches, c] })

// The server's ids for what was temporary: the trip's, and each catch's (a local catch has id = its key until then).
export function applySwaps(trip, swaps) {
  let next = trip
  for (const s of swaps) {
    if (s.kind === 'trip' && next.id === s.temp) next = { ...next, id: s.real }
    if (s.kind === 'spot' && next.spot_id === s.temp) next = { ...next, spot_id: s.real }
    if (s.kind === 'catch') next = { ...next, catches: next.catches.map((c) => (c.key === s.temp ? { ...c, id: s.real } : c)) }
  }
  return next
}

export const catchCount = (trip) => (trip?.base ?? 0) + (trip?.catches.length ?? 0)

// ---------------------------------------------------------------- small helpers

// Put a value first in a short "recent" list.
export const bumpRecent = (list, value, max = 8) => [value, ...(list ?? []).filter((v) => v !== value)].slice(0, max)

// Items (species / lures) with the recently used ones first (in that order), the rest in their own order.
export function recentFirst(items, recent, idKey) {
  const rank = new Map((recent ?? []).map((id, i) => [id, i]))
  return [...items].sort((a, b) => (rank.get(a[idKey]) ?? 1e9) - (rank.get(b[idKey]) ?? 1e9))
}

// Metres between two positions (haversine)
export function metresBetween(a, b) {
  const rad = (d) => (d * Math.PI) / 180
  const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2
  return 2 * 6371000 * Math.asin(Math.min(1, Math.sqrt(h)))
}

// The spot with a position nearest here, within maxM metres (null when none is that close)
export function nearestSpot(spots, here, maxM = 2000) {
  let best = null
  for (const s of spots ?? []) {
    if (s.lat == null || s.lon == null) continue
    const d = metresBetween(here, { lat: s.lat, lon: s.lon })
    if (d <= maxM && (!best || d < best.metres)) best = { spot: s, metres: d }
  }
  return best
}

// 5025000 ms -> "1 h 23 min"; under a minute "just started"
export function elapsedText(startedAt, now = Date.now()) {
  const min = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 60000))
  if (min < 1) return 'just started'
  const h = Math.floor(min / 60)
  return h === 0 ? `${min} min` : `${h} h ${String(min % 60).padStart(2, '0')} min`
}

// A number typed as a length: '42,5' -> 42.5 ; junk, 0 and a metre-plus fish -> null
export function lengthFrom(text) {
  const n = Number(String(text ?? '').replace(',', '.'))
  return Number.isFinite(n) && n > 0 && n < 1000 ? Math.round(n * 10) / 10 : null
}
