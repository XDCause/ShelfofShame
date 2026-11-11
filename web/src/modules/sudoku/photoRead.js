// Reading a sudoku from a photo (2026-11-11): a newspaper's grid, read on this device (nothing is uploaded).
//   1. find the grid's outline (the long dark lines) - you can drag its four corners to fit
//   2. straighten it: a homography maps the four corners onto a square, and the square is sampled from the photo
//   3. each cell: ink in its middle (away from the grid lines)? Then match the ink's shape against digits drawn in
//      common newspaper typefaces (template matching: the best correlation wins)
// The result is checked by you on the type-in board before playing: reading photos isn't perfect.

// The 3 x 3 matrix taking each `from` point to its `to` point (four of each: [x, y]).
export function homography(from, to) {
  const A = [], b = []
  for (let i = 0; i < 4; i++) {
    const [x, y] = from[i], [X, Y] = to[i]
    A.push([x, y, 1, 0, 0, 0, -X * x, -X * y]); b.push(X)
    A.push([0, 0, 0, x, y, 1, -Y * x, -Y * y]); b.push(Y)
  }
  const h = solveLinear(A, b)
  return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1]]
}

export function applyH(H, x, y) {
  const w = H[2][0] * x + H[2][1] * y + H[2][2]
  return [(H[0][0] * x + H[0][1] * y + H[0][2]) / w, (H[1][0] * x + H[1][1] * y + H[1][2]) / w]
}

// Gaussian elimination with partial pivoting.
function solveLinear(A, b) {
  const n = b.length
  const M = A.map((row, i) => [...row, b[i]])
  for (let c = 0; c < n; c++) {
    let p = c
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r
    const top = M[c]
    M[c] = M[p]
    M[p] = top
    for (let r = 0; r < n; r++) {
      if (r === c || !M[c][c]) continue
      const f = M[r][c] / M[c][c]
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k]
    }
  }
  return M.map((row, i) => row[n] / row[i])
}

// Grey levels (0 dark .. 255 light) from an image, at most `max` px on its longer side.
export function greyOf(img, max = 1200) {
  const scale = Math.min(1, max / Math.max(img.naturalWidth || img.width, img.naturalHeight || img.height))
  const w = Math.round((img.naturalWidth || img.width) * scale), h = Math.round((img.naturalHeight || img.height) * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  ctx.drawImage(img, 0, 0, w, h)
  const data = ctx.getImageData(0, 0, w, h).data
  const g = new Uint8ClampedArray(w * h)
  for (let i = 0; i < w * h; i++) g[i] = (data[i * 4] * 299 + data[i * 4 + 1] * 587 + data[i * 4 + 2] * 114) / 1000
  return { g, w, h }
}

// Otsu's threshold: the grey level that best splits ink from paper.
export function otsu(g) {
  const hist = new Array(256).fill(0)
  for (const v of g) hist[v]++
  const total = g.length
  let sum = 0
  for (let i = 0; i < 256; i++) sum += i * hist[i]
  let sumB = 0, wB = 0, best = 0, cut = 128
  for (let t = 0; t < 256; t++) {
    wB += hist[t]
    if (!wB) continue
    const wF = total - wB
    if (!wF) break
    sumB += t * hist[t]
    const mB = sumB / wB, mF = (sum - sumB) / wF
    const between = wB * wF * (mB - mF) ** 2
    if (between > best) { best = between; cut = t }
  }
  return cut
}

// The grid's outline: the outermost rows and columns that are mostly ink (its border lines). Falls back to an inset box.
export function findGrid({ g, w, h }) {
  const cut = otsu(g)
  const rowInk = new Array(h).fill(0), colInk = new Array(w).fill(0)
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (g[y * w + x] <= cut) { rowInk[y]++; colInk[x]++ }
  const rows = rowInk.map((n, y) => (n > w * 0.3 ? y : -1)).filter((y) => y >= 0)
  const cols = colInk.map((n, x) => (n > h * 0.3 ? x : -1)).filter((x) => x >= 0)
  if (rows.length >= 2 && cols.length >= 2 && rows.at(-1) - rows[0] > h * 0.25 && cols.at(-1) - cols[0] > w * 0.25) {
    const [t, b, l, r] = [rows[0], rows.at(-1), cols[0], cols.at(-1)]
    return [[l, t], [r, t], [r, b], [l, b]]
  }
  return [[w * 0.06, h * 0.06], [w * 0.94, h * 0.06], [w * 0.94, h * 0.94], [w * 0.06, h * 0.94]]
}

const S = 450             // the straightened square
const T = 16              // each digit's shape, T x T

// The shape of the ink in a box of a grey image: its bounding box, scaled to T x T, mean 0.
function shape(get, x0, y0, x1, y1, cut) {
  let minX = x1, minY = y1, maxX = x0, maxY = y0, ink = 0
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) if (get(x, y) <= cut) {
    ink++
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  if (!ink) return null
  const bw = maxX - minX + 1, bh = maxY - minY + 1
  const side = Math.max(bw, bh)                      // keep the aspect: a 1 is tall and thin
  const ox = minX - (side - bw) / 2, oy = minY - (side - bh) / 2
  const v = new Float32Array(T * T)
  for (let j = 0; j < T; j++) for (let i = 0; i < T; i++) {
    let n = 0, dark = 0
    for (let yy = 0; yy < 3; yy++) for (let xx = 0; xx < 3; xx++) {
      const x = Math.floor(ox + ((i + (xx + 0.5) / 3) * side) / T), y = Math.floor(oy + ((j + (yy + 0.5) / 3) * side) / T)
      n++
      if (x >= minX && x <= maxX && y >= minY && y <= maxY && get(x, y) <= cut) dark++
    }
    v[j * T + i] = dark / n
  }
  const mean = v.reduce((a, b) => a + b, 0) / v.length
  let norm = 0
  for (let k = 0; k < v.length; k++) { v[k] -= mean; norm += v[k] * v[k] }
  norm = Math.sqrt(norm) || 1
  for (let k = 0; k < v.length; k++) v[k] /= norm
  return { v, ink, bw, bh }
}

// Each digit drawn in typefaces a newspaper might use (whichever this device has), as shapes.
let templates = null
function digitTemplates() {
  if (templates) return templates
  const fonts = ['Arial', 'Helvetica', 'Verdana', 'Times New Roman', 'Georgia', 'Courier New', 'sans-serif', 'serif']
  const size = 120
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  templates = []
  for (const font of fonts) {
    for (const weight of ['400', '700']) {
      for (let d = 1; d <= 9; d++) {
        ctx.fillStyle = '#fff'
        ctx.fillRect(0, 0, size, size)
        ctx.fillStyle = '#000'
        ctx.font = `${weight} ${size * 0.7}px ${font}`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(String(d), size / 2, size / 2)
        const px = ctx.getImageData(0, 0, size, size).data
        const s = shape((x, y) => px[(y * size + x) * 4], 0, 0, size, size, 128)
        if (s) templates.push({ d, v: s.v })
      }
    }
  }
  return templates
}

// Read the 81 digits inside the four corners (top-left, top-right, bottom-right, bottom-left), 0 = empty.
export function readGrid({ g, w, h }, corners) {
  const H = homography([[0, 0], [S, 0], [S, S], [0, S]], corners)
  const sq = new Uint8ClampedArray(S * S)
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const [sx, sy] = applyH(H, x + 0.5, y + 0.5)
    const ix = Math.min(w - 1, Math.max(0, Math.round(sx))), iy = Math.min(h - 1, Math.max(0, Math.round(sy)))
    sq[y * S + x] = g[iy * w + ix]
  }
  const cut = otsu(sq)
  const get = (x, y) => sq[y * S + x]
  const tpl = digitTemplates()
  const cell = S / 9
  const grid = []
  for (let r = 0; r < 9; r++) for (let c = 0; c < 9; c++) {
    const pad = cell * 0.16
    const x0 = Math.round(c * cell + pad), y0 = Math.round(r * cell + pad), x1 = Math.round((c + 1) * cell - pad), y1 = Math.round((r + 1) * cell - pad)
    const s = shape(get, x0, y0, x1, y1, cut)
    const area = (x1 - x0) * (y1 - y0)
    if (!s || s.ink < area * 0.025 || s.bh < (y1 - y0) * 0.3) { grid.push(0); continue }
    let best = 0, bestScore = -2
    for (const t of tpl) {
      let dot = 0
      for (let k = 0; k < t.v.length; k++) dot += t.v[k] * s.v[k]
      if (dot > bestScore) { bestScore = dot; best = t.d }
    }
    grid.push(best)
  }
  return grid
}
