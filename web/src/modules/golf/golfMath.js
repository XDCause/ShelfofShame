// Golf's live-round arithmetic (GolfPlay.jsx, HoleMap.jsx): no React and no network here, so each sum is tested on its
// own (tests/golfMath.test.js). Points are [lat, lon] like the API's maps (api/app/golf_map.py); the API's own sums are
// api/app/golfmath.py - stableford() here is the same rule, so the totals stay right while scores wait for signal.

const R = 6371008.8                      // the earth's mean radius in metres (as golfmath.py)
const rad = (d) => (d * Math.PI) / 180

// Haversine distance in metres between two [lat, lon] points.
export function metresBetween(a, b) {
  const p1 = rad(a[0])
  const p2 = rad(b[0])
  const h = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(rad(b[1] - a[1]) / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

// A shape's corners without the repeated closing one.
export const ring = (pts) => (pts?.length > 2 && pts[0][0] === pts.at(-1)[0] && pts[0][1] === pts.at(-1)[1] ? pts.slice(0, -1) : pts ?? [])

// The middle of a shape: the average of its corners (fine for a green; the same as golfmath.centre).
export function centre(pts) {
  const r = ring(pts)
  if (!r.length) return null
  return [r.reduce((s, p) => s + p[0], 0) / r.length, r.reduce((s, p) => s + p[1], 0) / r.length]
}

// Flat metres around an origin: x east, y north (equal scale: longitude shrunk by cos(latitude)). Fine across a hole.
export function flat(origin) {
  const k = Math.cos(rad(origin[0]))
  return {
    to: (p) => [rad(p[1] - origin[1]) * R * k, rad(p[0] - origin[0]) * R],
    from: ([x, y]) => [origin[0] + (y / R) * (180 / Math.PI), origin[1] + (x / (R * k)) * (180 / Math.PI)],
  }
}

const cross = (a, b) => a[0] * b[1] - a[1] * b[0]

// Is a flat point inside a flat polygon (ray casting)?
export function inside(p, poly) {
  let yes = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]
    const [xj, yj] = poly[j]
    if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) yes = !yes
  }
  return yes
}

// Front, middle and back of the green from where you stand, in metres. The middle is the green's centre; front and back
// are where the line from you through the middle enters and leaves the green's outline (standing on it: front 0).
// -> {front, middle, back} or null without a green.
export function greenDistances(from, green) {
  const pts = ring(green)
  if (!from || pts.length < 3) return null
  const mid = centre(pts)
  const middle = metresBetween(from, mid)
  const f = flat(from)
  const poly = pts.map(f.to)
  const m = f.to(mid)
  const len = Math.hypot(m[0], m[1])
  if (len < 0.5) {                       // standing on the middle: the green's nearest and farthest edges
    const ds = poly.map((p) => Math.hypot(p[0], p[1]))
    return { front: 0, middle, back: Math.max(...ds) }
  }
  const u = [m[0] / len, m[1] / len]
  const ts = []
  poly.forEach((a, i) => {
    const b = poly[(i + 1) % poly.length]
    const d = [b[0] - a[0], b[1] - a[1]]
    const den = cross(u, d)
    if (Math.abs(den) < 1e-12) return
    const t = cross(a, d) / den
    const s = cross(a, u) / den
    if (s >= -1e-9 && s <= 1 + 1e-9 && t >= 0) ts.push(t)
  })
  if (!ts.length) {                      // (an odd shape the line misses: the corners' spread along it)
    const along = poly.map((p) => p[0] * u[0] + p[1] * u[1])
    return { front: Math.max(0, Math.min(...along)), middle, back: Math.max(0, ...along) }
  }
  const on = inside([0, 0], poly)
  return { front: on ? 0 : Math.min(...ts), middle, back: Math.max(...ts) }
}

// Where a hole's drawing starts and points: the tee (the hole line's first point, else the first tee's middle) and the
// green's middle (else the line's end). null when the hole has neither.
export function teeAndPin(map) {
  if (!map) return { tee: null, pin: null }
  const line = map.line?.length >= 2 ? map.line : null
  const tee = line ? line[0] : map.tees?.length ? centre(map.tees[0]) : null
  const pin = map.green?.length >= 3 ? centre(map.green) : line ? line.at(-1) : null
  return { tee, pin }
}

// The hole's drawing frame: flat metres turned so the tee is at the bottom and the green at the top (SVG y grows down).
//   toXY([lat, lon]) -> [x, y]   fromXY([x, y]) -> [lat, lon]   box: {x, y, w, h} (the viewBox), bearing (degrees)
export function holeFrame(map, pad = 25) {
  const { tee, pin } = teeAndPin(map)
  if (!tee || !pin) return null
  const f = flat(tee)
  const [ex, ey] = f.to(pin)
  const a = Math.atan2(ex, ey)          // bearing from north, clockwise
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const toXY = (p) => {
    const [x, y] = f.to(p)
    return [x * cos - y * sin, -(x * sin + y * cos)]
  }
  const fromXY = ([X, Y]) => {
    const x2 = X
    const y2 = -Y
    return f.from([x2 * cos + y2 * sin, -x2 * sin + y2 * cos])
  }
  const pts = [tee, pin, ...(map.line ?? []), ...ring(map.green), ...(map.tees ?? []).flat(), ...(map.fairways ?? []).flat()].map(toXY)
  let x0 = Math.min(...pts.map((p) => p[0])) - pad
  let x1 = Math.max(...pts.map((p) => p[0])) + pad
  const y0 = Math.min(...pts.map((p) => p[1])) - pad
  const y1 = Math.max(...pts.map((p) => p[1])) + pad
  const minW = Math.max(90, (y1 - y0) * 0.5)     // never a thin strip: at least half as wide as it's tall
  if (x1 - x0 < minW) {
    const mid = (x0 + x1) / 2
    x0 = mid - minW / 2
    x1 = mid + minW / 2
  }
  return { toXY, fromXY, box: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }, bearing: ((a * 180) / Math.PI + 360) % 360, tee, pin }
}

// ---------------------------------------------------------------- scoring

// Stableford points (golfmath.stableford): net par 2, net birdie 3, net bogey 1, worse or a pick-up 0.
export const stableford = (strokes, par, got) => (strokes == null ? 0 : Math.max(0, par + got - strokes + 2))

// A hole's score in a word, for its colour: eagle (or better), birdie, par, bogey, double (or worse); pick-up: double.
export function scoreKind(strokes, par, pickedUp = false) {
  if (pickedUp) return 'double'
  if (strokes == null) return null
  const d = strokes - par
  return d <= -2 ? 'eagle' : d === -1 ? 'birdie' : d === 0 ? 'par' : d === 1 ? 'bogey' : 'double'
}
export const KIND_NAMES = { eagle: 'eagle or better', birdie: 'birdie', par: 'par', bogey: 'bogey', double: 'double bogey or worse' }

// A score against par as golfers write it: E, +3, -1 (a real minus sign).
export const toParText = (n) => (n == null ? '–' : n === 0 ? 'E' : n > 0 ? `+${n}` : `−${-n}`)

export const BLANK = { strokes: null, putts: null, fairway: null, penalties: 0, sand: 0, first_putt_m: null, picked_up: false }

// A hole's score from the API's hole row.
export const scoreOf = (h) => ({ strokes: h.strokes ?? null, putts: h.putts ?? null, fairway: h.fairway ?? null,
  penalties: h.penalties ?? 0, sand: h.sand ?? 0, first_putt_m: h.first_putt_m ?? null, picked_up: !!h.picked_up })

const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n))

// One change to a hole's score, kept valid the way the API checks it (putts + penalties never more than the strokes,
// a picked-up hole has no strokes). change: {strokes: +1 | -1} (from nothing: the par), {putts: +1 | -1} (from
// nothing: 2 or 1), {penalties / sand: +1 | -1}, {fairway: 'hit'} (again: off), {first_putt_m: 3} (again: off),
// {picked_up: true | false}, {clear: true}.
export function changeHole(s, par, change) {
  let n = { ...s }
  if (change.clear) return { ...BLANK }
  if ('strokes' in change) {
    n.picked_up = false
    n.strokes = n.strokes == null ? par : clamp(n.strokes + change.strokes, 1, 20)
  }
  if ('putts' in change) {
    n.putts = n.putts == null ? (change.putts > 0 ? 2 : 1) : clamp(n.putts + change.putts, 0, 10)
    if (n.putts === 0) n.first_putt_m = null
  }
  if ('penalties' in change) n.penalties = clamp(n.penalties + change.penalties, 0, 10)
  if ('sand' in change) n.sand = clamp(n.sand + change.sand, 0, 10)
  if ('fairway' in change) n.fairway = n.fairway === change.fairway ? null : change.fairway
  if ('first_putt_m' in change) n.first_putt_m = n.first_putt_m === change.first_putt_m ? null : change.first_putt_m
  if ('picked_up' in change) {
    n = { ...n, picked_up: change.picked_up }
    if (change.picked_up) n.strokes = null
  }
  // keep it possible: more putts or penalties than strokes lifts the strokes (or, when the strokes went down, the putts)
  const used = (n.putts ?? 0) + n.penalties
  if (n.strokes != null && used > n.strokes) {
    if ('strokes' in change) n.putts = n.putts == null ? null : Math.max(0, n.strokes - n.penalties)
    if ((n.putts ?? 0) + n.penalties > n.strokes) n.strokes = Math.min(20, (n.putts ?? 0) + n.penalties)
  }
  return n
}

export const entered = (s) => s && (s.strokes != null || s.picked_up)

// The round so far from the holes (API rows: par, received) and this device's scores {hole_no: score}: holes entered,
// strokes and par of the holes with a score, against par, Stableford points.
export function roundTotals(holes, scores) {
  let played = 0
  let strokes = 0
  let par = 0
  let points = 0
  let scored = 0
  for (const h of holes) {
    const s = scores[h.hole_no]
    if (!entered(s)) continue
    played++
    points += stableford(s.strokes, h.par, h.received ?? 0)
    if (s.strokes != null) { scored++; strokes += s.strokes; par += h.par }
  }
  return { played, of: holes.length, strokes, points, toPar: scored ? strokes - par : null }
}

// First-putt length quick picks: [label, metres kept].
export const PUTT_PICKS = [['<1 m', 0.6], ['1–2 m', 1.5], ['2–4 m', 3], ['4–8 m', 6], ['8+ m', 10]]

// ---------------------------------------------------------------- shots and clubs

// The club for a distance: the one in the bag whose carry is nearest (clubs without a carry, or out of the bag, skipped).
export function suggestClub(clubs, metres) {
  if (metres == null) return null
  let best = null
  for (const c of clubs ?? []) {
    if (c.in_bag === false || !c.carry_m || c.kind === 'putter') continue
    if (!best || Math.abs(c.carry_m - metres) < Math.abs(best.carry_m - metres)) best = c
  }
  return best
}

// A hole's marked shots with each one's distance (to the next marked shot), like the API's answer.
export function shotDistances(shots) {
  return shots.map((s, i) => {
    const next = shots[i + 1]
    return { ...s, metres: next ? Math.round(metresBetween([s.lat, s.lon], [next.lat, next.lon])) : null }
  })
}

// ---------------------------------------------------------------- the queue (changes waiting for signal)

// Add a change to the waiting list. A hole's score replaces the one waiting for the same hole (the API keeps only the
// latest anyway, and its PUT is safe to resend); shots keep their order (a mark and its undo must go in turn).
export function enqueue(queue, item) {
  if (item.kind === 'hole') return [...queue.filter((q) => !(q.kind === 'hole' && q.hole === item.hole)), item]
  return [...queue, item]
}

// What to do with a failed send: 'retry' (no network, the server's having trouble, or signed out: after signing in
// again) or 'drop' (the server said no: sending it again won't help; an undo of a shot that's already gone is done).
export const failure = (err) => (err?.status == null || err.status >= 500 || [401, 408, 429].includes(err.status) ? 'retry' : 'drop')
