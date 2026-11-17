// Golf's plain helpers (no React, no API: tested in web/src/tests/golfFormat.test.js): how a score, a handicap and a
// stat read, which part of your game is furthest behind ("work on this"), and a hole's map turned into an SVG sketch.

// A score against par: "E", "+3", "−2" (a real minus sign).
export const toPar = (n) => (n == null ? '—' : n === 0 ? 'E' : n > 0 ? `+${n}` : `−${Math.abs(n)}`)

// A handicap: "18.4"; a plus handicap (better than scratch, stored below 0) reads "+1.2".
export const hcpText = (v) => {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return n < 0 ? `+${Math.abs(n).toFixed(1)}` : n.toFixed(1)
}

export const pct = (v) => (v == null ? '—' : `${Math.round(Number(v))}%`)
export const num = (v, digits = 1) => (v == null ? '—' : Number(v).toFixed(digits).replace(/\.0+$/, ''))
export const plural = (n, one, many = `${one}s`) => `${(n ?? 0).toLocaleString()} ${n === 1 ? one : many}`
export const HOLE_SETS = { 18: '18 holes', front: 'Front 9', back: 'Back 9' }
// Which holes a round is ('18' / 'front' / 'back'). The API's answers carry the round's hole rows under `holes` (the
// scored holes replace the column), so it's read back from them: more than 9 = 18, starting at the 10th = the back.
export const holeSetOf = (holes) => (!Array.isArray(holes) ? holes ?? '18' : holes.length > 9 ? '18' : holes[0]?.hole_no >= 10 ? 'back' : 'front')
// "Back 9" / "9 holes" for a nine (the front nine of an 18 or a 9-hole course), null for 18
export const nineLabel = (holes) => ({ front: '9 holes', back: 'Back 9' })[holeSetOf(holes)] ?? null

// The stats "plays like" covers (api/app/golfmath.py BENCH): its name, how it's shown, and whether more is better.
export const PLAYS_LIKE = [
  { key: 'fairways', label: 'Fairways hit', unit: '%', higher: true },
  { key: 'gir', label: 'Greens in regulation', unit: '%', higher: true },
  { key: 'putts', label: 'Putts a round', unit: '', higher: false },
  { key: 'scrambling', label: 'Scrambling', unit: '%', higher: true },
  { key: 'three_putts', label: 'Three-putts a round', unit: '', higher: false },
  { key: 'penalties', label: 'Penalties a round', unit: '', higher: false },
]
export const statText = (key, v) => (v == null ? '—' : PLAYS_LIKE.find((p) => p.key === key)?.unit === '%' ? pct(v) : num(v))

// The stat whose "plays like" handicap is the highest: the part of your game furthest behind the rest. Needs two
// or more stats to compare (one alone isn't "weakest").
export function weakest(playsLike) {
  const got = Object.entries(playsLike ?? {}).filter(([, v]) => v != null)
  if (got.length < 2) return null
  return got.reduce((a, b) => (Number(b[1]) > Number(a[1]) ? b : a))[0]
}

// Strokes gained: the categories that have holes, worst first is the one to work on.
export const SG_LABELS = { off_tee: 'Off the tee', approach: 'Approach', around_green: 'Around the green', putting: 'Putting' }
export function sgRows(sg) {
  return Object.entries(SG_LABELS).filter(([k]) => sg?.[k]?.holes > 0 && sg[k].per18 != null)
    .map(([k, label]) => ({ key: k, label, value: Number(sg[k].per18), holes: sg[k].holes }))
}

// Points for a line chart: one a day (the last that day wins - two on one day would share a key), oldest first.
export function oneADay(rows) {
  const by = new Map()
  rows.forEach((r) => by.set(r.x, r))
  return [...by.values()]
}

// Score kinds as a bar list's rows.
export const KIND_LABELS = { eagles: 'Eagles or better', birdies: 'Birdies', pars: 'Pars', bogeys: 'Bogeys', doubles: 'Double bogeys', worse: 'Worse (or picked up)' }

// "4 4 3 5 4" (or with commas) -> [4, 4, 3, 5, 4]; null if any isn't a par (3 to 6) or the count is wrong.
export function parsePars(text, holes) {
  const got = String(text ?? '').trim().split(/[\s,;]+/).filter(Boolean).map(Number)
  if (!got.length) return []
  if (got.length !== holes || got.some((p) => !Number.isInteger(p) || p < 3 || p > 6)) return null
  return got
}

// A hole's map (OpenStreetMap shapes as [[lat, lon], ...]) as SVG paths, turned so the tee is at the bottom and the
// green at the top. Longitude is shrunk by cos(latitude) (a degree east is shorter than a degree north away from the
// equator); the view is fitted to the hole's line, its green and tees (a fairway or a lake shared with other holes
// is cut off at the edge). -> {viewBox, line, green, tees, fairways, bunkers, water} or null.
export function holeSketch(map, pad = 25) {
  const line = map?.line
  if (!line || line.length < 2) return null
  const [lat0, lon0] = line[0]
  const k = Math.cos((lat0 * Math.PI) / 180)
  const xy = ([lat, lon]) => [(lon - lon0) * k * 111320, (lat - lat0) * 110574]
  const [ex, ey] = xy(line.at(-1))
  const a = Math.atan2(ex, ey)                       // the hole's direction (from north)
  const [ca, sa] = [Math.cos(a), Math.sin(a)]
  const turn = (p) => { const [x, y] = xy(p); return [x * ca - y * sa, -(x * sa + y * ca)] }   // screen y runs down
  const shape = (pts) => (pts?.length ? pts.map(turn) : null)
  const shapes = (list) => (list ?? []).map(shape).filter(Boolean)
  const out = { line: shape(line), green: shape(map.green), tees: shapes(map.tees), fairways: shapes(map.fairways),
    bunkers: shapes(map.bunkers), water: shapes(map.water) }
  const frame = [...out.line, ...(out.green ?? []), ...out.tees.flat()]
  let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity]
  frame.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y) })
  // at least 70 m wide (a straight hole is a thin line) and twice as tall as wide at most
  const h = y1 - y0 + 2 * pad
  const w = Math.max(x1 - x0 + 2 * pad, 70, h / 2)
  const cx = (x0 + x1) / 2
  const r = (n) => Math.round(n * 10) / 10
  const d = (pts, close) => `M${pts.map(([x, y]) => `${r(x)} ${r(y)}`).join('L')}${close ? 'Z' : ''}`
  return {
    viewBox: `${r(cx - w / 2)} ${r(y0 - pad)} ${r(w)} ${r(h)}`, width: r(w), height: r(h),
    line: d(out.line, false), green: out.green && d(out.green, true), tees: out.tees.map((p) => d(p, true)),
    fairways: out.fairways.map((p) => d(p, true)), bunkers: out.bunkers.map((p) => d(p, true)), water: out.water.map((p) => d(p, true)),
  }
}
