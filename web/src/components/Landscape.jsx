import { memo, useId } from 'react'

// A drawn landscape for a banner when you haven't given a page a picture of your own: layered ridges
// at dusk, mist between them, pines on the near hills, a low sun (or a moon and stars), in a hobby's
// colour. Drawn here as one SVG (no image files, nothing downloaded), the same every time for the same
// seed. Scenes:
//   peaks   sharp mountains        hills   soft rolling hills     forest  hills covered in pines
//   coast   headland over the sea  night   hills under stars and a moon
const W = 1600
const H = 600

// A small seeded random number generator (mulberry32): the same seed draws the same landscape.
function random(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))
const toHex = (rgb) => `#${rgb.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0')).join('')}`
// a + (b - a) * t, per channel
const mix = (a, b, t) => toHex(hex(a).map((v, i) => v + (hex(b)[i] - v) * t))

// A ridge line across the picture: midpoint displacement (jagged for peaks) or a few sine waves (hills).
function ridge(rand, { base, height, rough, smooth }) {
  if (smooth) {
    const waves = [0, 1, 2].map((i) => ({ f: (1 + i * 1.7 + rand()) / W * Math.PI * 2, p: rand() * 6.3, a: height / (1 + i * 1.6) }))
    return Array.from({ length: 65 }, (_, i) => {
      const x = (i / 64) * W
      return [x, base - waves.reduce((y, w) => y + Math.sin(x * w.f + w.p) * w.a * 0.5 + w.a * 0.5, 0) / 1.6]
    })
  }
  let pts = [[0, base - rand() * height], [W, base - rand() * height]]
  let spread = height
  for (let level = 0; level < 7; level += 1) {
    const next = [pts[0]]
    for (let i = 1; i < pts.length; i += 1) {
      const [x0, y0] = pts[i - 1]
      const [x1, y1] = pts[i]
      next.push([(x0 + x1) / 2, Math.min(base, (y0 + y1) / 2 + (rand() - 0.55) * spread)], pts[i])
    }
    pts = next
    spread *= rough
  }
  return pts
}

const area = (pts, bottom = H) => `M0 ${bottom} L${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L')} L${W} ${bottom} Z`

// Pines standing on a ridge: little stacked triangles, as one path.
function pines(rand, pts, size, every) {
  let d = ''
  const at = (x) => {
    const i = pts.findIndex(([px]) => px >= x)
    if (i <= 0) return pts[0][1]
    const [x0, y0] = pts[i - 1]
    const [x1, y1] = pts[i]
    return y0 + ((x - x0) / (x1 - x0 || 1)) * (y1 - y0)
  }
  for (let x = rand() * every; x < W; x += every * (0.5 + rand())) {
    const h = size * (0.6 + rand() * 0.8)
    const w = h * 0.32
    const y = at(x) + 4
    d += `M${x.toFixed(1)} ${(y - h).toFixed(1)} L${(x - w * 0.62).toFixed(1)} ${(y - h * 0.48).toFixed(1)} L${(x - w * 0.36).toFixed(1)} ${(y - h * 0.5).toFixed(1)} `
      + `L${(x - w).toFixed(1)} ${y.toFixed(1)} L${(x + w).toFixed(1)} ${y.toFixed(1)} L${(x + w * 0.36).toFixed(1)} ${(y - h * 0.5).toFixed(1)} `
      + `L${(x + w * 0.62).toFixed(1)} ${(y - h * 0.48).toFixed(1)} Z `
  }
  return d
}

// strip: a short, wide crop (a card's picture strip) shows the horizon rather than the foot of the hills.
function Landscape({ scene = 'peaks', hue = '#84a85c', seed = 7, className = '', strip = false }) {
  const id = useId().replace(/:/g, '')
  const rand = random(seed * 9973 + scene.length * 131)
  const night = scene === 'night'
  const coast = scene === 'coast'

  // The palette: a deep sky over a warm horizon, ridges going from hazy (far) to near-black pine (near).
  const skyTop = mix(night ? '#08111a' : '#1a2a2a', hue, 0.2)
  const skyMid = mix(night ? '#1b2d40' : '#5d6a55', hue, 0.34)
  const horizon = mix(night ? '#46607a' : '#f0b47a', hue, night ? 0.3 : 0.26)
  const glow = night ? '#dfe8ef' : '#ffd8a3'
  const haze = mix(horizon, night ? '#243844' : '#55695a', 0.5)
  const near = mix('#09100c', hue, 0.06)
  const layers = coast ? 3 : 5
  const sunX = W * (0.56 + rand() * 0.26)
  const sunY = H * (night ? 0.24 : 0.5)
  const seaLine = H * 0.66

  const ridges = Array.from({ length: layers }, (_, i) => {
    const t = i / (layers - 1)
    const base = coast ? seaLine + 2 : H * (0.5 + t * 0.42)
    const height = (scene === 'peaks' ? 260 : 150) * (1 - t * 0.45)
    const pts = ridge(rand, { base, height, rough: scene === 'peaks' ? 0.56 : 0.5, smooth: scene !== 'peaks' || t > 0.7 })
    return { pts, t, colour: mix(haze, near, Math.pow(t, 0.75)) }
  })
  // The coast's headland: a cliff on one side running down into the sea.
  const headland = coast && (() => {
    const pts = ridge(rand, { base: H * 0.78, height: 170, rough: 0.5, smooth: true })
      .map(([x, y]) => [x, x > W * 0.48 ? y + Math.pow((x - W * 0.48) / (W * 0.18), 2) * 160 : y])
      .map(([x, y]) => [x, Math.min(y, H + 10)])
    return pts
  })()
  const stars = night && Array.from({ length: 90 }, () => [rand() * W, rand() * H * 0.55, rand() * 1.4 + 0.3, rand() * 0.7 + 0.2])

  return (
    <svg className={`landscape ${className}`} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={strip ? 'xMidYMid slice' : 'xMidYMax slice'} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`sky${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={skyTop} />
          <stop offset="0.45" stopColor={skyMid} />
          <stop offset="0.78" stopColor={horizon} />
        </linearGradient>
        <radialGradient id={`sun${id}`} cx={sunX} cy={sunY} r={night ? 260 : 520} gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor={glow} stopOpacity={night ? 0.35 : 0.75} />
          <stop offset="0.25" stopColor={horizon} stopOpacity="0.35" />
          <stop offset="1" stopColor={horizon} stopOpacity="0" />
        </radialGradient>
        <linearGradient id={`mist${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={glow} stopOpacity="0" />
          <stop offset="0.6" stopColor={glow} stopOpacity={night ? 0.06 : 0.12} />
          <stop offset="1" stopColor={glow} stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`sea${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={mix(horizon, skyMid, 0.35)} />
          <stop offset="1" stopColor={mix(skyTop, near, 0.4)} />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#sky${id})`} />
      {stars && stars.map(([x, y, r, o], i) => <circle key={i} cx={x.toFixed(1)} cy={y.toFixed(1)} r={r.toFixed(2)} fill="#fff" opacity={o.toFixed(2)} />)}
      <rect width={W} height={H} fill={`url(#sun${id})`} />
      <circle cx={sunX} cy={sunY} r={night ? 30 : 42} fill={glow} opacity={night ? 0.9 : 0.85} />
      {coast && <rect y={seaLine} width={W} height={H - seaLine} fill={`url(#sea${id})`} />}
      {coast && <rect x={sunX - 70} y={seaLine} width="140" height={H - seaLine} fill={glow} opacity="0.08" />}
      {ridges.map(({ pts, t, colour }, i) => (
        <g key={i}>
          <path d={area(pts, coast ? seaLine + 4 : H)} fill={colour} />
          {(scene === 'forest' || scene === 'peaks' || scene === 'night') && t > 0.5 && (
            <path d={pines(rand, pts, 30 + t * 34, 26 - t * 8)} fill={colour} />
          )}
          {i < layers - 1 && !coast && (
            <rect y={Math.min(...pts.map(([, y]) => y)) - 10} width={W} height="120" fill={`url(#mist${id})`} />
          )}
        </g>
      ))}
      {headland && <path d={area(headland)} fill={near} />}
      {headland && <path d={pines(rand, headland.filter(([x]) => x < W * 0.5), 46, 20)} fill={near} />}
    </svg>
  )
}

export default memo(Landscape)
