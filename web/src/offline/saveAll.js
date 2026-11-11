// "Save everything now" (Settings > Offline copy): opens the app in a hidden frame and walks it through every page -
// Home, goals and each goal, the journal and each page, the calendar for this month and the next three, supplies,
// the wishlist, every hobby page - and opens each trip, hike and book. The service worker (sw.js) saves every answer
// the pages ask for, so they all open offline exactly as they look online. The frame can only read (sw.js refuses
// a change from a frame), and App takes its directions by message (SAVING in state.js).
import { api } from '../api.js'
import { MODULES } from '../modules/index.js'
import { noteSaved } from './offline.js'

let progress = null          // {done, total, label} while it runs
const listeners = new Set()
export const saveProgress = () => progress
export const onSaveProgress = (listener) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
const tell = (p) => {
  progress = p
  for (const listener of listeners) listener(p)
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// Every id under `key` in an API answer, however it's shaped (a list, {books: [...]}, goals with their children).
export function idsIn(answer, key, found = new Set()) {
  if (Array.isArray(answer)) for (const row of answer) idsIn(row, key, found)
  else if (answer && typeof answer === 'object') {
    if (answer[key] != null) found.add(answer[key])
    for (const value of Object.values(answer)) if (value && typeof value === 'object') idsIn(value, key, found)
  }
  return [...found]
}

const monthStart = (ahead) => {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() + ahead)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}

// Where the walk goes: {go: address} or {open: [kind, id]} (a panel, App's openThing).
export async function stops() {
  const go = (path, label) => ({ go: path, label })
  const list = [
    go('/', 'Home'), go('/goals', 'Goals'), go('/goals/todo', 'To-dos'), go('/journal', 'Journal'),
    go('/journal/calendar', 'Journal calendar'),
    ...[0, 1, 2, 3].map((n) => go(`/calendar?day=${monthStart(n)}`, 'Calendar')), go('/calendar?view=agenda', 'Calendar'),
    go('/hobbies', 'Hobbies'), go('/supplies', 'Supplies'), go('/wishlist', 'Wishlist'),
    ...MODULES.flatMap((m) => m.pages.map((p) => go(`/${m.id}/${p.path}`, `${m.name}: ${p.label}`))),
  ]
  const quietly = (call) => call().catch(() => [])
  const [goals, pages, trips, hikes, books, records] = await Promise.all([
    quietly(() => api.goals()), quietly(() => api.listPages({ limit: 1000 })), quietly(() => api.trips()),
    quietly(() => api.hikes()), quietly(() => api.books()), quietly(() => api.vinylRecords({ status: 'all' })),
  ])
  list.push(
    ...idsIn(goals, 'goal_id').map((id) => go(`/goals/${id}`, 'Goals')),
    ...idsIn(pages, 'page_id').map((id) => go(`/journal/${id}`, 'Journal pages')),
    ...idsIn(trips, 'trip_id').map((id) => ({ open: ['trip', id], label: 'Trips' })),
    ...idsIn(hikes, 'hike_id').map((id) => ({ open: ['hike', id], label: 'Hikes' })),
    ...idsIn(books, 'book_id').map((id) => ({ open: ['book', id], label: 'Books' })),
    ...idsIn(records, 'record_id').map((id) => ({ open: ['record', id], label: 'Records' })),
  )
  return list
}

// The frame's app has opened (signed in, its first page drawn).
async function opened(frame) {
  for (let waited = 0; waited < 30000; waited += 250) {
    await sleep(250)
    const doc = frame.contentDocument
    if (doc?.querySelector('.content main') && !doc.querySelector('.content main > .loading')) return
  }
  throw new Error("The app didn't open in the background - is it reachable?")
}

// Wait until the page has finished asking: no request in flight, and nothing new for a moment (at most 15 s).
async function settled(win, busy) {
  const start = Date.now()
  let seen = -1
  let still = Date.now()
  while (Date.now() - start < 15000) {
    await sleep(200)
    const now = win.performance.getEntriesByType('resource').length
    if (now !== seen || busy() > 0) { seen = now; still = Date.now() }
    else if (Date.now() - still >= 700) return
  }
}

export async function saveEverything() {
  if (progress) return null
  tell({ done: 0, total: 0, label: 'Getting ready' })
  const frame = document.createElement('iframe')
  frame.title = 'Saving for offline'
  frame.setAttribute('aria-hidden', 'true')
  frame.tabIndex = -1
  frame.className = 'offline-walker'
  Object.assign(frame.style, { width: `${window.innerWidth}px`, height: `${window.innerHeight}px` })   // (this device's layout)
  try {
    const list = await stops()
    frame.src = '/?otc-saving'
    document.body.append(frame)
    await opened(frame)
    const win = frame.contentWindow
    // (the frame's fetch, counted: a slow answer still in flight isn't "finished")
    let inFlight = 0
    const fetchFn = win.fetch.bind(win)
    win.fetch = (...args) => { inFlight++; return fetchFn(...args).finally(() => { inFlight-- }) }
    for (const [i, stop] of list.entries()) {
      tell({ done: i, total: list.length, label: stop.label })
      win.performance.clearResourceTimings()
      win.postMessage({ otcSave: stop.go ? { go: stop.go } : { open: stop.open } }, window.location.origin)
      await settled(win, () => inFlight)
    }
    noteSaved()
    return { pages: list.length }
  } finally {
    frame.remove()
    tell(null)
  }
}
