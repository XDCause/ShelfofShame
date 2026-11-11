// The Sudoku engine (2026-11-11): everything the hobby needs to make, check, grade and explain puzzles - in the browser,
// so it works in the offline copy too, and no puzzle site is ever asked. Two sizes: the classic 9 x 9 (3 x 3 boxes) and
// a 16 x 16 giant (4 x 4 boxes, digits 1-9 then A-G). And a variant: Diagonal (X) sudoku, where both long diagonals hold
// every digit once too (9 x 9).
//
//   engineFor(size, variant) -> everything below for that size and variant ('classic' or 'x'); the module's own exports
//   are the classic 9 x 9 engine.
//   A grid is size*size numbers, row by row (0 = empty). Candidates are bit masks: bit d-1 set = d is still possible.
//   solveCount(grid, limit)   how many solutions (stops at `limit`): a real puzzle has exactly one
//   generate(rand, target)    a full grid, then clues taken away in symmetric pairs while the answer stays unique
//   findStep(values, cands)   the easiest logical step from here: its technique, what it places or rules out, which
//                             cells and areas it's about, and a sentence saying why (the hints and the grading use it)
//   grade(puzzle)             solve it step by step like a person: which techniques it needs -> its difficulty
//   hintFor(...)              the next hint for a game in progress (mistakes first)
//
// Techniques, easiest first (TECHNIQUES): singles; locked candidates; naked / hidden pairs, triples, quads; X-Wing,
// Swordfish, XY-Wing, XYZ-Wing. A puzzle none of them can finish is Extreme (it needs chains or trial and error).

export const SYMBOLS = '0123456789ABCDEFG'                  // 10-16 are A-G
export const sym = (d) => SYMBOLS[d] ?? ''
export const bit = (d) => 1 << (d - 1)
export const count = (m) => { let n = 0; while (m) { m &= m - 1; n++ } return n }

// A random number from a seed (the daily puzzle: the same for everyone on the same day). mulberry32.
export function seeded(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
export const seedOf = (text) => [...text].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) >>> 0, 2166136261)
const shuffle = (xs, rand) => { for (let i = xs.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [xs[i], xs[j]] = [xs[j], xs[i]] } return xs }

// level: 1 Easy (singles), 2 Medium (locked candidates), 3 Hard (subsets), 4 Expert (fish, wings); 5 = none of them.
export const TECHNIQUES = [
  { key: 'full_house', name: 'Full house', level: 1, about: 'A row, column or box has just one empty cell left: it takes the one digit that unit is missing.' },
  { key: 'hidden_single', name: 'Hidden single', level: 1, about: 'A digit has only one place left in a row, column or box, even if that cell could hold other digits.' },
  { key: 'naked_single', name: 'Naked single', level: 1, about: 'A cell can only hold one digit: every other digit is already in its row, column or box.' },
  { key: 'pointing', name: 'Pointing pair / triple', level: 2, about: "In a box, a digit's places all lie in one row (or column). Whichever it is, that row needs it in this box - so it can't go anywhere else in that row." },
  { key: 'claiming', name: 'Box / line reduction', level: 2, about: "In a row (or column), a digit's places all lie in one box. So that box gets it in this row - it can't go anywhere else in the box." },
  { key: 'naked_pair', name: 'Naked pair', level: 3, about: 'Two cells in a unit can only hold the same two digits. Those digits go in those two cells, so no other cell in the unit can have them.' },
  { key: 'hidden_pair', name: 'Hidden pair', level: 3, about: 'Two digits can only go in the same two cells of a unit. Those cells must hold those digits, so any other candidates in them can go.' },
  { key: 'naked_triple', name: 'Naked triple', level: 3, about: 'Three cells in a unit hold only three digits between them: those digits are used up there, so the rest of the unit loses them.' },
  { key: 'hidden_triple', name: 'Hidden triple', level: 3, about: 'Three digits can only go in the same three cells of a unit: those cells hold them, so their other candidates go.' },
  { key: 'naked_quad', name: 'Naked quad', level: 3, about: 'Four cells in a unit hold only four digits between them: the rest of the unit loses those digits.' },
  { key: 'x_wing', name: 'X-Wing', level: 4, about: 'A digit fits in exactly two places in each of two rows, and they line up in the same two columns. It must sit on one diagonal of that rectangle, so those two columns lose it everywhere else (and the same with rows and columns swapped).' },
  { key: 'swordfish', name: 'Swordfish', level: 4, about: "An X-Wing with three rows: a digit's places in three rows all fall in the same three columns, so those columns lose it everywhere else." },
  { key: 'xy_wing', name: 'XY-Wing', level: 4, about: 'A pivot cell holds XY; one cell it sees holds XZ and another holds YZ. Whichever the pivot is, one of those two cells is Z - so any cell seeing both of them can\'t be Z.' },
  { key: 'xyz_wing', name: 'XYZ-Wing', level: 4, about: 'Like an XY-Wing, but the pivot holds XYZ: one of the three cells is Z, so a cell seeing all three can\'t be Z.' },
]
export const TECHNIQUE = Object.fromEntries(TECHNIQUES.map((t) => [t.key, t]))
export const DIFFICULTIES = ['Easy', 'Medium', 'Hard', 'Expert', 'Extreme']
export const SIZES = [9, 16]
// A 16 x 16 at Expert or harder can take minutes to make (each clue removed needs a full uniqueness check): not offered.
export const DIFFICULTIES_FOR = { 9: DIFFICULTIES, 16: DIFFICULTIES.slice(0, 3) }
export const VARIANTS = { classic: 'Classic', x: 'Diagonal (X)' }
// Diagonal (X) puzzles get hard fast as clues go: Expert ones are rare to find, so X offers Easy to Hard.
export const X_DIFFICULTIES = DIFFICULTIES.slice(0, 3)

const combos = (xs, n, start = 0, pick = [], out = []) => {
  if (pick.length === n) { out.push([...pick]); return out }
  for (let i = start; i <= xs.length - (n - pick.length); i++) { pick.push(xs[i]); combos(xs, n, i + 1, pick, out); pick.pop() }
  return out
}
const list = (xs) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs.at(-1)}`)

const made = {}
export const engineFor = (size = 9, variant = 'classic') => (made[`${size}-${variant}`] ??= makeEngine(size, variant === 'x' ? 'x' : 'classic'))

function makeEngine(N, variant) {
  const B = Math.round(Math.sqrt(N))
  const CELLS = N * N
  const ALL = (1 << N) - 1
  const range = (n) => Array.from({ length: n }, (_, i) => i)
  const ROWS = range(N).map((r) => range(N).map((c) => r * N + c))
  const COLS = range(N).map((c) => range(N).map((r) => r * N + c))
  const BOXES = range(N).map((b) => range(N).map((i) => (Math.floor(b / B) * B + Math.floor(i / B)) * N + (b % B) * B + (i % B)))
  // Diagonal (X): the two long diagonals are units too (after the boxes).
  const DIAGS = variant === 'x' ? [range(N).map((i) => i * N + i), range(N).map((i) => i * N + (N - 1 - i))] : []
  const UNITS = [...ROWS, ...COLS, ...BOXES, ...DIAGS]    // rows, then columns, then boxes (then the diagonals)
  const onDiag = (c, k) => DIAGS[k]?.includes(c)
  const rowOf = (c) => Math.floor(c / N)
  const colOf = (c) => c % N
  const boxOf = (c) => Math.floor(rowOf(c) / B) * B + Math.floor(colOf(c) / B)
  const PEERS = range(CELLS).map((c) => [...new Set([...ROWS[rowOf(c)], ...COLS[colOf(c)], ...BOXES[boxOf(c)],
    ...(onDiag(c, 0) ? DIAGS[0] : []), ...(onDiag(c, 1) ? DIAGS[1] : [])])].filter((p) => p !== c))
  const PEER_SET = PEERS.map((p) => new Set(p))
  const sees = (a, b) => PEER_SET[a].has(b)
  const digitsOf = (m) => { const out = []; for (let d = 1; d <= N; d++) if (m & bit(d)) out.push(d); return out }
  const onlyDigit = (m) => digitsOf(m)[0]
  const cellName = (c) => `r${rowOf(c) + 1}c${colOf(c) + 1}`
  const unitName = (u) => (u < N ? `row ${u + 1}` : u < 2 * N ? `column ${u - N + 1}` : u < 3 * N ? `box ${u - 2 * N + 1}`
    : u === 3 * N ? 'the ↘ diagonal' : 'the ↙ diagonal')
  const cellsText = (cs) => list(cs.map(cellName))
  const digitsText = (ds) => list(ds.map(sym))

  // ---- grids as text: digits, A-G for 10-16, 0 or . for empty
  const parse = (text) => {
    const s = String(text ?? '').toUpperCase().replace(/[^0-9A-G.]/g, '').replace(/\./g, '0')
    if (s.length !== CELLS) return null
    const g = [...s].map((ch) => SYMBOLS.indexOf(ch))
    return g.every((d) => d >= 0 && d <= N) ? g : null
  }
  const toText = (grid) => grid.map(sym).join('')

  function candidates(values) {
    return values.map((v, c) => {
      if (v) return 0
      let used = 0
      for (const p of PEERS[c]) if (values[p]) used |= bit(values[p])
      return ALL & ~used
    })
  }

  function conflicts(values) {
    const bad = new Set()
    for (const unit of UNITS) {
      const seen = {}
      for (const c of unit) if (values[c]) (seen[values[c]] ??= []).push(c)
      for (const cs of Object.values(seen)) if (cs.length > 1) cs.forEach((c) => bad.add(c))
    }
    return bad
  }

  function solveCount(grid, limit = 2, out = null) {
    const v = [...grid]
    if (conflicts(v).size) return 0
    let found = 0
    const rows = new Array(N).fill(0), cols = new Array(N).fill(0), boxes = new Array(N).fill(0), diag = [0, 0]
    const d0 = range(CELLS).map((c) => onDiag(c, 0)), d1 = range(CELLS).map((c) => onDiag(c, 1))
    const mark = (c, b, on) => {
      const f = on ? (m) => m | b : (m) => m & ~b
      rows[rowOf(c)] = f(rows[rowOf(c)]); cols[colOf(c)] = f(cols[colOf(c)]); boxes[boxOf(c)] = f(boxes[boxOf(c)])
      if (d0[c]) diag[0] = f(diag[0])
      if (d1[c]) diag[1] = f(diag[1])
    }
    for (let c = 0; c < CELLS; c++) if (v[c]) mark(c, bit(v[c]), true)
    const go = () => {
      let best = -1, bestMask = 0, bestN = N + 1
      for (let c = 0; c < CELLS; c++) {
        if (v[c]) continue
        const m = ALL & ~(rows[rowOf(c)] | cols[colOf(c)] | boxes[boxOf(c)] | (d0[c] ? diag[0] : 0) | (d1[c] ? diag[1] : 0))
        const n = count(m)
        if (n === 0) return false
        if (n < bestN) { best = c; bestMask = m; bestN = n; if (n === 1) break }
      }
      if (best < 0) {
        found++
        if (out && found === 1) out.push(...v)
        return found >= limit
      }
      for (const d of digitsOf(bestMask)) {
        v[best] = d
        mark(best, bit(d), true)
        if (go()) return true
        v[best] = 0
        mark(best, bit(d), false)
      }
      return false
    }
    go()
    return found
  }

  function solve(grid) {
    const out = []
    return solveCount(grid, 2, out) === 1 ? out : null
  }

  // A random full grid: 9 x 9 by backtracking; 16 x 16 from a pattern, shuffled (digits, rows in each band, the bands,
  // columns in each stack, the stacks, and maybe turned) - backtracking a 16 x 16 can take far too long.
  function fullGrid(rand) {
    if (N === 9 || variant === 'x') {
      const v = new Array(CELLS).fill(0)
      const go = (c) => {
        if (c === CELLS) return true
        let used = 0
        for (const p of PEERS[c]) if (v[p]) used |= bit(v[p])
        for (const d of shuffle(digitsOf(ALL & ~used), rand)) {
          v[c] = d
          if (go(c + 1)) return true
        }
        v[c] = 0
        return false
      }
      go(0)
      return v
    }
    const digit = shuffle(range(N).map((i) => i + 1), rand)
    const lines = () => shuffle(range(B), rand).flatMap((band) => shuffle(range(B), rand).map((i) => band * B + i))
    const rs = lines(), cs = lines(), turn = rand() < 0.5
    const v = new Array(CELLS)
    for (let r = 0; r < N; r++) {
      for (let c = 0; c < N; c++) {
        const [rr, cc] = turn ? [cs[c], rs[r]] : [rs[r], cs[c]]
        v[r * N + c] = digit[(B * (rr % B) + Math.floor(rr / B) + cc) % N]
      }
    }
    return v
  }

  const step = (key, data) => ({ technique: key, name: TECHNIQUE[key].name, level: TECHNIQUE[key].level, units: [], cells: [], eliminate: [], ...data })

  function fullHouse(values) {
    for (let u = 0; u < UNITS.length; u++) {
      const empty = UNITS[u].filter((c) => !values[c])
      if (empty.length !== 1) continue
      let have = 0
      for (const c of UNITS[u]) if (values[c]) have |= bit(values[c])
      const d = onlyDigit(ALL & ~have)
      return step('full_house', { place: { cell: empty[0], digit: d }, units: [u], cells: empty,
        text: `${unitName(u)} has one empty cell left, ${cellName(empty[0])}: it takes the missing ${sym(d)}.` })
    }
    return null
  }

  function hiddenSingle(values, cands) {
    for (const u of [...range(N).map((i) => i + 2 * N), ...range(2 * N), ...DIAGS.map((_, k) => 3 * N + k)]) {     // boxes first: easiest to see
      for (let d = 1; d <= N; d++) {
        const spots = UNITS[u].filter((c) => cands[c] & bit(d))
        if (spots.length === 1 && !UNITS[u].some((c) => values[c] === d)) {
          return step('hidden_single', { place: { cell: spots[0], digit: d }, units: [u], cells: spots, digits: [d],
            text: `In ${unitName(u)}, ${sym(d)} can only go in ${cellName(spots[0])}.` })
        }
      }
    }
    return null
  }

  function nakedSingle(values, cands) {
    for (let c = 0; c < CELLS; c++) {
      if (!values[c] && count(cands[c]) === 1) {
        const d = onlyDigit(cands[c])
        return step('naked_single', { place: { cell: c, digit: d }, cells: [c], digits: [d],
          text: `${cellName(c)} can only be ${sym(d)}: every other digit is already in its row, column or box.` })
      }
    }
    return null
  }

  function locked(values, cands) {
    for (let b = 2 * N; b < 3 * N; b++) {
      for (let d = 1; d <= N; d++) {
        const spots = UNITS[b].filter((c) => cands[c] & bit(d))
        if (spots.length < 2) continue
        for (const [lines, of, kind] of [[ROWS, rowOf, 'row'], [COLS, colOf, 'column']]) {
          const line = of(spots[0])
          if (!spots.every((c) => of(c) === line)) continue
          const elim = lines[line].filter((c) => !spots.includes(c) && cands[c] & bit(d))
          if (elim.length) {
            return step('pointing', { units: [b, kind === 'row' ? line : N + line], cells: spots, digits: [d], eliminate: elim.map((cell) => ({ cell, digit: d })),
              text: `In ${unitName(b)}, ${sym(d)} can only go in ${kind} ${line + 1} (${cellsText(spots)}). So ${kind} ${line + 1} gets its ${sym(d)} in this box: take ${sym(d)} out of ${cellsText(elim)}.` })
          }
        }
      }
    }
    for (let u = 0; u < 2 * N; u++) {
      for (let d = 1; d <= N; d++) {
        const spots = UNITS[u].filter((c) => cands[c] & bit(d))
        if (spots.length < 2) continue
        const box = boxOf(spots[0])
        if (!spots.every((c) => boxOf(c) === box)) continue
        const elim = BOXES[box].filter((c) => !spots.includes(c) && cands[c] & bit(d))
        if (elim.length) {
          return step('claiming', { units: [u, 2 * N + box], cells: spots, digits: [d], eliminate: elim.map((cell) => ({ cell, digit: d })),
            text: `In ${unitName(u)}, ${sym(d)} can only go in box ${box + 1} (${cellsText(spots)}). So box ${box + 1}'s ${sym(d)} is in ${unitName(u)}: take ${sym(d)} out of ${cellsText(elim)}.` })
        }
      }
    }
    return null
  }

  const NAKED = { 2: 'naked_pair', 3: 'naked_triple', 4: 'naked_quad' }
  function nakedSubset(values, cands, n) {
    for (let u = 0; u < UNITS.length; u++) {
      const open = UNITS[u].filter((c) => !values[c] && count(cands[c]) >= 2 && count(cands[c]) <= n)
      for (const set of combos(open, n)) {
        const union = set.reduce((m, c) => m | cands[c], 0)
        if (count(union) !== n) continue
        const elim = []
        for (const c of UNITS[u]) {
          if (values[c] || set.includes(c)) continue
          for (const d of digitsOf(cands[c] & union)) elim.push({ cell: c, digit: d })
        }
        if (elim.length) {
          const ds = digitsOf(union)
          return step(NAKED[n], { units: [u], cells: set, digits: ds, eliminate: elim,
            text: `In ${unitName(u)}, ${cellsText(set)} can only hold ${digitsText(ds)} between them. Those digits are used up there, so take them out of the rest of ${unitName(u)}.` })
        }
      }
    }
    return null
  }

  const HIDDEN = { 2: 'hidden_pair', 3: 'hidden_triple' }
  function hiddenSubset(values, cands, n) {
    for (let u = 0; u < UNITS.length; u++) {
      const missing = digitsOf(ALL).filter((d) => !UNITS[u].some((c) => values[c] === d))
      for (const ds of combos(missing, n)) {
        const mask = ds.reduce((m, d) => m | bit(d), 0)
        const cells = UNITS[u].filter((c) => cands[c] & mask)
        if (cells.length !== n || ds.some((d) => !cells.some((c) => cands[c] & bit(d)))) continue
        const elim = []
        for (const c of cells) for (const d of digitsOf(cands[c] & ~mask)) elim.push({ cell: c, digit: d })
        if (elim.length) {
          return step(HIDDEN[n], { units: [u], cells, digits: ds, eliminate: elim,
            text: `In ${unitName(u)}, ${digitsText(ds)} can only go in ${cellsText(cells)}. Those cells must hold them, so their other candidates can go.` })
        }
      }
    }
    return null
  }

  const FISH = { 2: 'x_wing', 3: 'swordfish' }
  function fish(values, cands, n) {
    for (let d = 1; d <= N; d++) {
      for (const [base, cover, posOf, baseKind, coverKind, coverOffset, baseOffset] of
        [[ROWS, COLS, colOf, 'row', 'column', N, 0], [COLS, ROWS, rowOf, 'column', 'row', 0, N]]) {
        const lines = []
        for (let i = 0; i < N; i++) {
          const spots = base[i].filter((c) => cands[c] & bit(d))
          if (spots.length >= 2 && spots.length <= n) lines.push({ i, spots })
        }
        for (const set of combos(lines, n)) {
          const covers = [...new Set(set.flatMap((l) => l.spots.map(posOf)))]
          if (covers.length !== n) continue
          const baseIdx = set.map((l) => l.i)
          const elim = covers.flatMap((k) => cover[k].filter((c) => cands[c] & bit(d) && !baseIdx.includes(baseKind === 'row' ? rowOf(c) : colOf(c))))
          if (elim.length) {
            const spots = set.flatMap((l) => l.spots)
            return step(FISH[n], { units: [...baseIdx.map((i) => i + baseOffset), ...covers.map((k) => k + coverOffset)], cells: spots, digits: [d],
              eliminate: elim.map((cell) => ({ cell, digit: d })),
              text: `${sym(d)} fits only in ${coverKind}s ${list(covers.map((k) => k + 1).sort((a, b) => a - b))} in ${baseKind}s ${list(baseIdx.map((i) => i + 1))} (${cellsText(spots)}). Each of those ${baseKind}s needs a ${sym(d)} there, so those ${coverKind}s get theirs from these ${baseKind}s: take ${sym(d)} out of ${cellsText(elim)}.` })
          }
        }
      }
    }
    return null
  }

  function xyWing(values, cands) {
    const bi = range(CELLS).filter((c) => !values[c] && count(cands[c]) === 2)
    for (const pivot of bi) {
      const [x, y] = digitsOf(cands[pivot])
      const wings = bi.filter((c) => c !== pivot && sees(pivot, c) && count(cands[c] & cands[pivot]) === 1)
      for (const a of wings) {
        for (const b of wings) {
          if (a >= b) continue
          const za = cands[a] & ~cands[pivot], zb = cands[b] & ~cands[pivot]
          if (!za || za !== zb || (cands[a] & cands[pivot]) === (cands[b] & cands[pivot])) continue
          const z = onlyDigit(za)
          const elim = PEERS[a].filter((c) => c !== pivot && c !== b && sees(b, c) && cands[c] & za)
          if (elim.length) {
            return step('xy_wing', { cells: [pivot, a, b], digits: [x, y, z], eliminate: elim.map((cell) => ({ cell, digit: z })),
              text: `${cellName(pivot)} is ${sym(x)} or ${sym(y)}. It sees ${cellName(a)} (${digitsText(digitsOf(cands[a]))}) and ${cellName(b)} (${digitsText(digitsOf(cands[b]))}): whichever the pivot is, one of those two is ${sym(z)}. So ${cellsText(elim)}, seeing both, can't be ${sym(z)}.` })
          }
        }
      }
    }
    return null
  }

  function xyzWing(values, cands) {
    for (let pivot = 0; pivot < CELLS; pivot++) {
      if (values[pivot] || count(cands[pivot]) !== 3) continue
      const wings = PEERS[pivot].filter((c) => !values[c] && count(cands[c]) === 2 && (cands[c] & ~cands[pivot]) === 0)
      for (const a of wings) {
        for (const b of wings) {
          if (a >= b || (cands[a] | cands[b]) !== cands[pivot]) continue
          const zm = cands[a] & cands[b]
          if (count(zm) !== 1) continue
          const z = onlyDigit(zm)
          const elim = PEERS[pivot].filter((c) => c !== a && c !== b && sees(a, c) && sees(b, c) && cands[c] & zm)
          if (elim.length) {
            return step('xyz_wing', { cells: [pivot, a, b], digits: digitsOf(cands[pivot]), eliminate: elim.map((cell) => ({ cell, digit: z })),
              text: `${cellName(pivot)} is ${digitsText(digitsOf(cands[pivot]))}; ${cellName(a)} and ${cellName(b)} are ${digitsText(digitsOf(cands[a]))} and ${digitsText(digitsOf(cands[b]))}. One of the three is ${sym(z)} whatever happens, so ${cellsText(elim)}, seeing all three, can't be ${sym(z)}.` })
          }
        }
      }
    }
    return null
  }

  const FINDERS = [
    ['full_house', (v) => fullHouse(v)], ['hidden_single', hiddenSingle], ['naked_single', nakedSingle], ['locked', locked],
    ['naked_pair', (v, c) => nakedSubset(v, c, 2)], ['hidden_pair', (v, c) => hiddenSubset(v, c, 2)],
    ['naked_triple', (v, c) => nakedSubset(v, c, 3)], ['hidden_triple', (v, c) => hiddenSubset(v, c, 3)], ['naked_quad', (v, c) => nakedSubset(v, c, 4)],
    ['x_wing', (v, c) => fish(v, c, 2)], ['xy_wing', xyWing], ['xyz_wing', xyzWing], ['swordfish', (v, c) => fish(v, c, 3)],
  ]

  function findStep(values, cands, only = null) {
    for (const [key, finder] of FINDERS) {
      if (only && key !== only && !(key === 'locked' && (only === 'pointing' || only === 'claiming'))) continue
      const s = finder(values, cands)
      if (s && (!only || s.technique === only)) return s
    }
    return null
  }

  function apply(values, cands, s) {
    if (s.place) {
      const { cell, digit } = s.place
      values[cell] = digit
      cands[cell] = 0
      for (const p of PEERS[cell]) cands[p] &= ~bit(digit)
    }
    for (const e of s.eliminate) cands[e.cell] &= ~bit(e.digit)
  }

  // Singles with plenty of clues = Easy; singles on a sparse grid, or locked candidates = Medium; subsets = Hard;
  // fish / wings = Expert; beyond the app's techniques = Extreme. (9 x 9: 34+ clues; 16 x 16: 140+.)
  const EASY_CLUES = N === 9 ? 34 : 140
  function difficultyOf(level, clues) {
    if (level === 1) return clues >= EASY_CLUES ? 'Easy' : 'Medium'
    return DIFFICULTIES[level - 1]
  }

  function grade(puzzle) {
    const values = [...puzzle]
    const cands = candidates(values)
    const used = {}
    let level = 1, steps = 0
    while (values.some((v) => !v)) {
      const s = findStep(values, cands)
      if (!s) { level = 5; break }
      apply(values, cands, s)
      used[s.technique] = (used[s.technique] ?? 0) + 1
      level = Math.max(level, s.level)
      if (++steps > CELLS * 20) { level = 5; break }
    }
    const clues = puzzle.filter(Boolean).length
    const order = (k) => TECHNIQUES.findIndex((t) => t.key === k)
    const hardest = Object.keys(used).sort((a, b) => TECHNIQUE[b].level - TECHNIQUE[a].level || order(b) - order(a))[0] ?? null
    return { level, difficulty: difficultyOf(level, clues), techniques: used, hardest: level === 5 ? null : hardest, clues, logical: level < 5, size: N, variant }
  }

  // Clues removed in symmetric pairs (a half turn), in random order, while the answer stays unique. `keep` = stop with
  // this many clues left; 0 = as few as possible (a minimal puzzle: 9 x 9 only - a 16 x 16 would take too long).
  function makePuzzle(rand, keep = 0) {
    const solution = fullGrid(rand)
    const puzzle = [...solution]
    const order = shuffle(range(Math.ceil(CELLS / 2)), rand)
    let clues = CELLS
    for (const c of order) {
      if (keep && clues <= keep) break
      const m = CELLS - 1 - c
      const was = [puzzle[c], puzzle[m]]
      puzzle[c] = 0
      puzzle[m] = 0
      if (solveCount(puzzle, 2) !== 1) {
        puzzle[c] = was[0]
        puzzle[m] = was[1]
      } else {
        clues -= c === m ? 1 : 2
      }
    }
    return { puzzle, solution }
  }

  // How many clues to leave for a difficulty: 9 x 9 Easy keeps 36-40, the rest go minimal; a 16 x 16 always keeps some.
  const keepFor = (difficulty, rand) => {
    if (N === 9 && variant === 'x') return { Easy: 34, Medium: 27, Hard: 23 }[difficulty] + Math.floor(rand() * 3) || 0   // (X: the diagonals do a lot)
    if (N === 9) return difficulty === 'Easy' ? 36 + Math.floor(rand() * 5) : 0
    return { Easy: 150, Medium: 124, Hard: 108, Expert: 100, Extreme: 96 }[difficulty] + Math.floor(rand() * 6)
  }

  function generate(rand, { difficulty = 'Medium', technique = null, budgetMs = N === 9 ? 6000 : 12000, onTry = null } = {}) {
    const want = technique ? TECHNIQUE[technique].level : DIFFICULTIES.indexOf(difficulty) + 1
    const started = Date.now()
    let best = null, bestGap = 99
    for (let tries = 1; ; tries++) {
      const { puzzle, solution } = makePuzzle(rand, technique ? (N === 9 ? 0 : 104) : keepFor(difficulty, rand))
      const g = grade(puzzle)
      onTry?.(tries)
      const hit = technique ? g.hardest === technique || (g.techniques[technique] && g.level === want) : g.difficulty === difficulty
      if (hit) return { puzzle, solution, grade: g, tries }
      const gap = Math.abs(g.level - want) + (technique && g.techniques[technique] ? 0 : 0.5)
      if (gap < bestGap) { best = { puzzle, solution, grade: g, tries }; bestGap = gap }
      if (Date.now() - started > budgetMs) return { ...best, closest: true, tries }
    }
  }

  // The next hint for a game: a wrong digit first; notes that rule out the right answer; then the easiest step from the
  // current position (your notes count as eliminations, so a hint never repeats what they already say).
  function hintFor(values, notes, solution) {
    const wrong = values.map((v, c) => (v && v !== solution[c] ? c : -1)).filter((c) => c >= 0)
    if (wrong.length) {
      return { technique: 'mistake', name: 'A mistake', level: 0, cells: wrong, units: [], eliminate: [],
        text: `${cellsText(wrong)} ${wrong.length === 1 ? "isn't" : "aren't"} right. Take ${wrong.length === 1 ? 'it' : 'them'} out and look again.` }
    }
    const plain = candidates(values)
    const cands = [...plain]
    const badNotes = []
    for (let c = 0; c < CELLS; c++) {
      if (values[c] || !notes[c]) continue
      if (!(notes[c] & bit(solution[c]))) badNotes.push(c)
      else cands[c] &= notes[c]
    }
    if (badNotes.length) {
      return { technique: 'note_mistake', name: 'A note that rules out the answer', level: 0, cells: badNotes, units: [], eliminate: [],
        text: `Your notes in ${cellsText(badNotes)} leave out the digit that goes there. Check them again (or fill notes afresh).` }
    }
    const s = findStep(values, cands)
    if (s) return byYourNotes(s, values, plain, cands)
    const fewest = Math.min(...values.map((x, j) => (x ? N + 1 : count(cands[j]))))
    const c = values.findIndex((v, i) => !v && count(cands[i]) === fewest)
    return { technique: 'stuck', name: 'Beyond the techniques here', level: 5, cells: [c], units: [], eliminate: [], place: { cell: c, digit: solution[c] },
      text: `None of the techniques in the app help from here (it needs chains or trial and error). ${cellName(c)} is ${sym(solution[c])} - apply to place it.` }
  }

  // A hint found with the player's notes can lean on digits they've ruled out themselves (or an earlier hint did) that
  // the board alone still allows. Say so - "9 can only go in r6c5" looks wrong when r9c5 could still be 9 on the board
  // (user, 2026-11-11).
  function byYourNotes(s, values, plain, cands) {
    const naked = s.technique === 'naked_single'
    const mask = naked || !s.digits?.length ? ALL : s.digits.reduce((m, d) => m | bit(d), 0)
    const seen = new Set([...s.cells, ...s.units.flatMap((u) => UNITS[u])])
    const ruled = []
    for (const c of seen) {
      if (values[c]) continue
      const gone = plain[c] & ~cands[c] & mask
      if (gone) ruled.push(`${list(digitsOf(gone).map(sym))} in ${cellName(c)}`)
    }
    if (!ruled.length) return s
    const shown = ruled.length > 4 ? [...ruled.slice(0, 4), `${ruled.length - 4} more`] : ruled
    if (naked) {
      const { cell, digit } = s.place
      return { ...s, text: `Going by your notes, ${cellName(cell)} can only be ${sym(digit)}: you've already ruled out ${list(shown)}.` }
    }
    return { ...s, text: `${s.text} (This goes by your notes: you've already ruled out ${list(shown)}, which the board alone still allows.)` }
  }

  const isSolved = (values, solution) => values.every((v, i) => v === solution[i])

  // Practice: solve the puzzle with easier steps up to the moment `technique` is the next move. Answers that position -
  // the digits placed, every cell's candidates (with the easier steps' eliminations, for the notes), the step itself and
  // how many steps led there - or null if it never comes up.
  function practiceStart(puzzle, technique) {
    const values = [...puzzle]
    const cands = candidates(values)
    for (let steps = 0; steps < CELLS * 20; steps++) {
      const s = findStep(values, cands)
      if (!s) return null
      if (s.technique === technique) return { values, cands, step: s, steps }
      apply(values, cands, s)
      if (values.every(Boolean)) return null
    }
    return null
  }

  return { N, B, CELLS, ALL, ROWS, COLS, BOXES, DIAGS, UNITS, PEERS, variant, onDiag, rowOf, colOf, boxOf, sees, digitsOf, cellName, unitName, parse, toText,
    candidates, conflicts, solveCount, solve, fullGrid, findStep, apply, grade, difficultyOf, makePuzzle, generate, hintFor, isSolved, practiceStart }
}

// The classic 9 x 9, as plain functions.
const E9 = engineFor(9)
export const { ALL, ROWS, COLS, BOXES, UNITS, PEERS, rowOf, colOf, boxOf, sees, digitsOf, cellName, unitName, parse, toText, candidates,
  conflicts, solveCount, solve, fullGrid, findStep, apply, grade, difficultyOf, makePuzzle, generate, hintFor, isSolved, practiceStart } = E9
