// Nitrox and gas maths done in the browser (pure functions, metric: metres, bar, litres). The planner and the dive
// profile use the API for decompression; these are the simple formulas a diver does on a slate. Learning and checking
// only - the dive computer and the training rule come first. o2 is a percentage (21 = air, 32 = EAN32).
const SEA = 10          // about 10 m of sea water per bar
const round1 = (v) => Math.round((v + 1e-9) * 10) / 10
const round2 = (v) => Math.round((v + 1e-9) * 100) / 100

export const ata = (depth) => depth / SEA + 1

// The partial pressure of oxygen (bar) breathing o2 % at depth metres.
export const ppO2 = (o2, depth) => round2((o2 / 100) * ata(depth))

// Maximum operating depth (m) for a gas at a ppO2 limit (1.4 working, 1.6 contingency), to 0.1 m.
export const mod = (o2, limit = 1.4) => round1((limit / (o2 / 100) - 1) * SEA)

// Equivalent air depth (m): the depth on air with the same nitrogen load (narcosis / decompression "feel").
export const ead = (o2, depth) => round1(((1 - o2 / 100) / 0.79) * (depth + SEA) - SEA)

// The richest whole-percent mix whose ppO2 stays at or under the limit at that depth (never above 100).
export const bestMix = (depth, limit = 1.4) => Math.min(100, Math.floor((limit / ata(depth)) * 100 + 1e-9))

// Surface air consumption (L/min at the surface): litres breathed, per minute, per bar of ambient pressure.
// Returns null when anything is missing or doesn't make sense.
export const sac = ({ startBar, endBar, tankL, minutes, avgDepth }) => {
  const nums = [startBar, endBar, tankL, minutes, avgDepth].map(Number)
  if ([startBar, endBar, tankL, minutes, avgDepth].some((v) => v === '' || v == null) || nums.some((n) => Number.isNaN(n))) return null
  const [s, e, t, m, d] = nums
  if (m <= 0 || t <= 0 || s <= e || d < 0) return null
  return round1(((s - e) * t) / m / ata(d))
}

// A minutes figure from seconds: 754 -> "12:34" style clock for the profile's readout.
export const clockOf = (seconds) => {
  const s = Math.max(0, Math.round(seconds ?? 0))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export const CAVEAT = 'For learning and checking - your dive computer and training rule.'
