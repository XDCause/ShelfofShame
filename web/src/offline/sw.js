// The offline copy's service worker: a script the browser keeps on this device and runs between the app and the
// network (Settings > Offline copy turns it on: offline/offline.js registers it; off removes it and the copy).
// vite.config.js (offlineWorker) builds it into dist/sw.js with BUILD filled in: the app's own files and a version.
//
//   The app's files (index.html, scripts, styles, fonts): saved when it's turned on, so the app opens with no server.
//   API reads (GET /api/...): asked of the server first, as always; each answer is saved. When the server can't be
//     reached (the PC at home is off, asleep or restarting for an update) the saved answer is given instead, marked
//     X-OTC-Saved (api.js shows the "Offline" banner).
//   Changes (POST, PATCH...): passed on. With the server unreachable they're refused at once with a clear message:
//     the copy is read-only (2026-11-11). A frame (the "Save everything now" walk, offline/saveAll.js) may only read.
const BUILD = { version: 'dev', files: [] } // (filled in by vite.config.js)

const SHELL = `otc-shell-${BUILD.version}`
const DATA = 'otc-data'
const WAIT = 6000          // ms before a read that hasn't answered is given the saved copy (it still updates it later)
const WAIT_DOWN = 2500     // ...once the server is known to be unreachable
const NOT_SAVED = ['/api/auth/']       // sign-in answers aren't kept (except /api/auth/status: the app opens on it)
let down = false           // the last attempt to reach the server failed

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(BUILD.files)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name.startsWith('otc-shell-') && name !== SHELL) await caches.delete(name)
    await self.clients.claim()
  })())
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return            // other sites: the browser as usual
  if (req.method !== 'GET') return event.respondWith(change(event))
  if (url.pathname.startsWith('/api/')) {
    if (req.headers.has('range') || (NOT_SAVED.some((p) => url.pathname.startsWith(p)) && url.pathname !== '/api/auth/status')) return
    return event.respondWith(read(event))
  }
  if (req.mode === 'navigate') return event.respondWith(page(req))
  event.respondWith(file(req))
})

const answer = (status, detail) => new Response(JSON.stringify({ detail }), {
  status, headers: { 'Content-Type': 'application/json', 'X-OTC-Offline': '1' },
})
const OFFLINE = "You're offline: the app at home can't be reached, so changes can't be saved. What you see is the copy " +
  'saved on this device.'

// A change. Never from the "Save everything now" frame; with the server unreachable, a quick check and a clear no.
async function change(event) {
  const client = event.clientId && await self.clients.get(event.clientId)
  if (client?.frameType === 'nested') return answer(503, 'Saving for offline only reads.')
  if (!down) return fetch(event.request).catch(() => { down = true; return answer(503, OFFLINE) })
  const stop = new AbortController()
  const timer = setTimeout(() => stop.abort(), 8000)
  try {
    const res = await fetch(event.request, { signal: stop.signal })
    down = false
    return res
  } catch {
    return answer(503, OFFLINE)
  } finally {
    clearTimeout(timer)
  }
}

// Worth keeping: a good answer the app reads (JSON) or shows (a photo).
const keepable = (res) => res.ok && res.status === 200 && /^(application\/json|image\/)/.test(res.headers.get('content-type') ?? '')

async function keep(req, res) {
  const headers = new Headers(res.headers)
  headers.set('X-OTC-Saved', new Date().toISOString())
  const cache = await caches.open(DATA)
  await cache.put(req.url, new Response(await res.blob(), { status: res.status, statusText: res.statusText, headers }))
}

// The saved answer: this exact address, or else the newest saved one that differs only in dates. Pages ask for
// "today"-based ranges (?start=2026-11-01...), different addresses on a later day: an older range beats nothing, and
// the banner says it's the saved copy. Anything else that differs (a search, a filter) isn't a stand-in.
const DATE = /^\d{4}-\d{2}(-\d{2})?$/
function onlyDatesDiffer(a, b) {
  if (a.pathname !== b.pathname) return false
  const [x, y] = [a.searchParams, b.searchParams]
  const keys = new Set([...x.keys(), ...y.keys()])
  return [...keys].every((k) => x.get(k) === y.get(k) || (DATE.test(x.get(k) ?? '') && DATE.test(y.get(k) ?? '')))
}
async function saved(req) {
  const cache = await caches.open(DATA)
  const exact = await cache.match(req.url)
  if (exact) return exact
  const want = new URL(req.url)
  const near = (await cache.keys()).filter((k) => onlyDatesDiffer(new URL(k.url), want))
  return near.length ? cache.match(near.at(-1)) : null      // (keys are in the order saved: the last is the newest)
}

// Is the server there at all? (A slow answer - a shop lookup can take a minute - isn't "offline".)
async function reachable() {
  const stop = new AbortController()
  const timer = setTimeout(() => stop.abort(), 2500)
  try {
    return (await fetch('/api/health', { signal: stop.signal, cache: 'no-store' })).ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

async function read(event) {
  const req = event.request
  const asked = fetch(req)
  // (saved even when it answers after the saved copy was given; attached first, so it copies before the page reads it)
  event.waitUntil(asked.then((res) => { down = false; return keepable(res) ? keep(req, res.clone()) : null },
    () => { down = true }))
  const late = new Promise((resolve) => setTimeout(() => resolve('late'), down ? WAIT_DOWN : WAIT))
  try {
    const first = await Promise.race([asked, late])
    if (first !== 'late') return first
    if (!down && await reachable()) return await asked          // just slow: wait for it
    down = true
    return (await saved(req)) ?? await asked                    // nothing saved: wait for the server after all
  } catch {
    return (await saved(req)) ?? answer(503, "You're offline, and this wasn't saved on this device.")
  }
}

// A page of the app (any address: the app finds its page itself): the server's index.html, or the saved one.
async function page(req) {
  try {
    const res = await Promise.race([fetch(req), new Promise((_, no) => setTimeout(no, down ? WAIT_DOWN : WAIT))])
    down = false
    return res
  } catch {
    down = true
    return (await caches.match('/index.html', { cacheName: SHELL })) ?? answer(503, OFFLINE)
  }
}

// The app's own files: saved ones first (their names change with their contents), anything else saved as it's used.
async function file(req) {
  const hit = await caches.match(req)
  if (hit) return hit
  const res = await fetch(req)
  if (res.ok && res.status === 200) {
    const copy = res.clone()
    caches.open(SHELL).then((c) => c.put(req, copy))
  }
  return res
}
