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

// Pines standing on a ridge: little stacked triangles, as one path. Only where the ridge is (its own x range) and,
// for the coast's headland, only on land (above maxY, the sea's line) - never in the air. (A tree's base is checked
// to be on its ridge by e2e/ui_audit.py: the "art" check.)
function pines(rand, pts, size, every, maxY = Infinity) {
  let d = ''
  const at = (x) => {
    const i = pts.findIndex(([px]) => px >= x)
    if (i <= 0) return pts[0][1]
    const [x0, y0] = pts[i - 1]
    const [x1, y1] = pts[i]
    return y0 + ((x - x0) / (x1 - x0 || 1)) * (y1 - y0)
  }
  const [from, to] = [pts[0][0], pts.at(-1)[0]]
  for (let x = from + rand() * every; x < to; x += every * (0.5 + rand())) {
    const h = size * (0.6 + rand() * 0.8)
    const w = h * 0.32
    const ground = at(x)
    if (ground > maxY) continue
    const y = ground + 4
    d += `M${x.toFixed(1)} ${(y - h).toFixed(1)} L${(x - w * 0.62).toFixed(1)} ${(y - h * 0.48).toFixed(1)} L${(x - w * 0.36).toFixed(1)} ${(y - h * 0.5).toFixed(1)} `
      + `L${(x - w).toFixed(1)} ${y.toFixed(1)} L${(x + w).toFixed(1)} ${y.toFixed(1)} L${(x + w * 0.36).toFixed(1)} ${(y - h * 0.5).toFixed(1)} `
      + `L${(x + w * 0.62).toFixed(1)} ${(y - h * 0.48).toFixed(1)} Z `
  }
  return d
}

// The time of day: the sky's colours before the area's hue is mixed in, and whether the sun shows.
//   golden    late afternoon (the first look; Home keeps it)    dawn      lilac sky, a peach horizon
//   blue      after sunset: cool, a glow where the sun went     overcast  soft grey, cloud cover, no sun
const TIMES = {
  golden: { top: '#1a2a2a', mid: '#5d6a55', horizon: '#f0b47a', glow: '#ffd8a3', haze: '#55695a', sun: true },
  dawn: { top: '#1c2236', mid: '#6a5a7a', horizon: '#f2a690', glow: '#ffe1d2', haze: '#5c5a6c', sun: true },
  blue: { top: '#0b1626', mid: '#2a4964', horizon: '#8eb2c8', glow: '#e6f1fb', haze: '#3a5468', sun: false },
  overcast: { top: '#1f2729', mid: '#4a5553', horizon: '#a1aaa0', glow: '#e1e6df', haze: '#5b655f', sun: false },
}

// strip: a short, wide crop (a card's picture strip) shows the horizon rather than the foot of the hills.
// time and extras (clouds, birds, snow, lake, fog, aurora) make each area's picture its own; with neither given it's
// drawn exactly as it always was (Home's).
function Landscape({ scene = 'peaks', hue = '#84a85c', seed = 7, className = '', strip = false, time = 'golden', extras = [] }) {
  const id = useId().replace(/:/g, '')
  const rand = random(seed * 9973 + scene.length * 131)
  const more = random(seed * 7919 + 17)          // the extras' own dice, so they don't reshape the hills
  const night = scene === 'night'
  const coast = scene === 'coast'
  const has = (x) => extras.includes(x)
  const sky = TIMES[time] ?? TIMES.golden
  const varied = time !== 'golden' || extras.length > 0

  // The palette: a deep sky over a warm horizon, ridges going from hazy (far) to near-black pine (near).
  const skyTop = mix(night ? '#08111a' : sky.top, hue, 0.2)
  const skyMid = mix(night ? '#1b2d40' : sky.mid, hue, 0.34)
  const horizon = mix(night ? '#46607a' : sky.horizon, hue, night ? 0.3 : 0.26)
  const glow = night ? '#dfe8ef' : sky.glow
  const haze = mix(horizon, night ? '#243844' : sky.haze, 0.5)
  const near = mix('#09100c', hue, 0.06)
  const layers = coast ? 3 : 5
  const firstSunX = W * (0.56 + rand() * 0.26)
  const sunX = varied ? W * (0.14 + more() * 0.72) : firstSunX      // (anywhere along the sky, for a varied picture)
  const sunY = H * (night ? 0.24 : varied ? 0.42 + more() * 0.14 : 0.5)
  const seaLine = H * 0.66
  const showSun = night || sky.sun

  const ridges = Array.from({ length: layers }, (_, i) => {
    const t = i / (layers - 1)
    const base = coast ? seaLine + 2 : H * (0.5 + t * 0.42)
    const height = coast ? 70 + t * 40 : (scene === 'peaks' ? 260 : 150) * (1 - t * 0.45)
    const pts = ridge(rand, { base, height, rough: scene === 'peaks' ? 0.56 : 0.5, smooth: scene !== 'peaks' || t > 0.7 })
    // far hills fade into the haze (the coast's are all far: across the water, so never near-black)
    return { pts, t, colour: mix(haze, near, coast ? 0.1 + t * 0.3 : Math.pow(t, 0.75)) }
  })
  // The coast's headland: wooded hills on the left that slope smoothly down into the sea (gone under it by mid-way).
  const headland = coast && (() => {
    const ease = (v) => { const c = Math.max(0, Math.min(1, v)); return c * c * (3 - 2 * c) }   // smoothstep
    return ridge(rand, { base: H * 0.6, height: 110, rough: 0.5, smooth: true })
      .map(([x, y]) => [x, Math.min(y + ease((x - W * 0.2) / (W * 0.34)) * 340, H + 10)])
  })()
  const stars = night && Array.from({ length: 90 }, () => [rand() * W, rand() * H * 0.55, rand() * 1.4 + 0.3, rand() * 0.7 + 0.2])
  // Clouds: a few soft lit puffs (a sky full of them when it's overcast).
  const clouds = (has('clouds') || time === 'overcast') && Array.from({ length: time === 'overcast' ? 8 : 3 + Math.floor(more() * 3) }, () => ({
    x: more() * W, y: H * (0.06 + more() * (time === 'overcast' ? 0.36 : 0.28)), w: 160 + more() * 260, h: 16 + more() * 22, o: 0.3 + more() * 0.3 }))
  // Birds: a loose few, near the sun.
  const birds = has('birds') && Array.from({ length: 3 + Math.floor(more() * 4) }, () => ({
    x: Math.max(40, Math.min(W - 40, sunX + (more() - 0.5) * 560)), y: H * (0.12 + more() * 0.24), s: 7 + more() * 8 }))
  const lakeAfter = Math.floor(layers / 2)          // (a lake shows between the middle and the near hills)

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
        <radialGradient id={`glint${id}`}>
          <stop offset="0" stopColor={glow} stopOpacity="0.3" />
          <stop offset="1" stopColor={glow} stopOpacity="0" />
        </radialGradient>
        <filter id={`soft${id}`} x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="9" /></filter>
        <filter id={`veil${id}`} x="-10%" y="-100%" width="120%" height="300%"><feGaussianBlur stdDeviation="22" /></filter>
        <linearGradient id={`aurora${id}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#6fe0b0" stopOpacity="0" />
          <stop offset="0.35" stopColor="#6fe0b0" stopOpacity="0.55" />
          <stop offset="0.7" stopColor="#8f7ae6" stopOpacity="0.45" />
          <stop offset="1" stopColor="#8f7ae6" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={`sea${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={mix(horizon, skyMid, 0.35)} />
          <stop offset="1" stopColor={mix(skyTop, near, 0.4)} />
        </linearGradient>
      </defs>
      <rect width={W} height={H} fill={`url(#sky${id})`} />
      {stars && stars.map(([x, y, r, o], i) => <circle key={i} cx={x.toFixed(1)} cy={y.toFixed(1)} r={r.toFixed(2)} fill="#fff" opacity={o.toFixed(2)} />)}
      {/* northern lights: soft ribbons across the night sky */}
      {night && has('aurora') && [0, 1].map((k) => {
        const y0 = H * (0.12 + k * 0.1)
        return <path key={k} d={`M-40 ${y0 + 40} C ${W * 0.25} ${y0 - 60}, ${W * 0.45} ${y0 + 90}, ${W * 0.7} ${y0} S ${W + 40} ${y0 + 30}, ${W + 60} ${y0 - 10}`}
          stroke={`url(#aurora${id})`} strokeWidth={70 - k * 25} fill="none" filter={`url(#veil${id})`} opacity={0.8 - k * 0.25} />
      })}
      <rect width={W} height={H} fill={`url(#sun${id})`} opacity={showSun ? 1 : 0.55} />
      {showSun && <circle cx={sunX} cy={sunY} r={night ? 30 : 42} fill={glow} opacity={night ? 0.9 : 0.85} />}
      {clouds && clouds.map((c, i) => (
        <g key={`c${i}`} filter={`url(#soft${id})`} opacity={c.o} fill={mix(glow, skyMid, time === 'overcast' ? 0.45 : 0.3)}>
          <ellipse cx={c.x} cy={c.y} rx={c.w / 2} ry={c.h / 2} />
          <ellipse cx={c.x - c.w * 0.18} cy={c.y - c.h * 0.35} rx={c.w * 0.22} ry={c.h * 0.6} />
          <ellipse cx={c.x + c.w * 0.15} cy={c.y - c.h * 0.25} rx={c.w * 0.18} ry={c.h * 0.5} />
        </g>
      ))}
      {birds && birds.map((b, i) => (
        <path key={`b${i}`} d={`M${b.x - b.s} ${b.y} Q${b.x - b.s / 2} ${b.y - b.s * 0.55} ${b.x} ${b.y} Q${b.x + b.s / 2} ${b.y - b.s * 0.55} ${b.x + b.s} ${b.y}`}
          stroke={mix(near, skyMid, 0.25)} strokeWidth="2" fill="none" strokeLinecap="round" />
      ))}
      {coast && <rect y={seaLine} width={W} height={H - seaLine} fill={`url(#sea${id})`} />}
      {/* the sun on the water: a soft path of light, and a bright line where it meets the horizon */}
      {coast && <ellipse cx={sunX} cy={seaLine} rx="200" ry={H - seaLine} fill={`url(#glint${id})`} />}
      {coast && <ellipse cx={sunX} cy={seaLine + 2} rx="150" ry="3" fill={glow} opacity="0.45" />}
      {ridges.map(({ pts, t, colour }, i) => (
        <g key={i}>
          <path className="ridge" data-ridge={i} d={area(pts, coast ? seaLine + 4 : H)} fill={colour} />
          {/* snow on the far peaks: the ridge again, in snow, above a line a little under its highest point */}
          {has('snow') && t < 0.5 && (() => {
            const top = Math.min(...pts.map(([, y]) => y))
            return (
              <>
                <clipPath id={`snow${id}${i}`}><rect width={W} height={top + 38 + (1 - t) * 20} /></clipPath>
                <path d={area(pts, coast ? seaLine + 4 : H)} fill={mix('#f4f1ea', glow, 0.3)} opacity={0.78 - t * 0.5} clipPath={`url(#snow${id}${i})`} />
              </>
            )
          })()}
          {/* a lake in the valley: still water reflecting the sky, the nearer hills in front of it */}
          {has('lake') && i === lakeAfter && <>
            <rect y={H * 0.76} width={W} height={H * 0.24} fill={`url(#sea${id})`} />
            <ellipse cx={sunX} cy={H * 0.76} rx="180" ry={H * 0.16} fill={`url(#glint${id})`} />
            <rect y={H * 0.76} width={W} height="2" fill={glow} opacity="0.35" />
          </>}
          {/* low fog drifting between the nearer hills */}
          {has('fog') && t > 0.3 && t < 0.9 && (
            <ellipse cx={W * (0.3 + more() * 0.4)} cy={Math.min(...pts.map(([, y]) => y)) + 60} rx={W * 0.6} ry="34" fill={glow}
              opacity="0.16" filter={`url(#veil${id})`} />
          )}
          {(scene === 'forest' || scene === 'peaks' || scene === 'night') && t > 0.5 && (
            <path className="pines" data-ridge={i} d={pines(rand, pts, 30 + t * 34, 26 - t * 8)} fill={colour} />
          )}
          {i < layers - 1 && !coast && (
            <rect y={Math.min(...pts.map(([, y]) => y)) - 10} width={W} height="120" fill={`url(#mist${id})`} />
          )}
        </g>
      ))}
      {headland && <path className="ridge" data-ridge="h" d={area(headland)} fill={near} />}
      {headland && <path className="pines" data-ridge="h" d={pines(rand, headland, 46, 20, seaLine - 24)} fill={near} />}
    </svg>
  )
}

export default memo(Landscape)
