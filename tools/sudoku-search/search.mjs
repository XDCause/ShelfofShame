// The sudoku search (2026-11-11): hunts for the hardest puzzles it can find, for the app's weekly and its own lists.
// Run it on a spare PC for hours (README.txt). Node.js 20+; no packages needed.
//
//   node search.mjs                     # until stopped (Ctrl+C - nothing is lost)
//   node search.mjs --hours 10          # stop after 10 hours
//   node search.mjs --threads 8         # use 8 threads (default: all but one)
//   node search.mjs --seeds my.tsv      # start from other puzzles (default: seeds.tsv, the app's own hardest)
//
// Every few minutes the best finds go to found.tsv - rank, score, clues, puzzle - the format
// load-sudoku-library.ps1 takes (copy it to the app PC: .\load-sudoku-library.ps1 -File found.tsv -List weekly).
//
// How hard is a puzzle (score)? Solve it with the app's techniques; where they stall, try every candidate and follow
// singles until a contradiction:
//   tier 1  a chain of singles cracks every stall: score 1000 + the longest "shortest chain" among the stalls (x10) -
//           19-28 steps is where the app's own list sits (very hard)
//   tier 2  some stall can't be cracked by ANY chain of singles, but one trial with every technique can - the level of
//           the famous "world's hardest" puzzles starts here (Inkala 2012, AI Escargot)
//   tier 3  needs trials inside trials
// Within a tier, fewer clues and fewer working trials score a little higher.
//
// The search: a pool of the hardest so far; each worker takes one, nudges it - swaps clues ({-1+1}, {-2+2}: always
// distinct cells, so the clue count never creeps up) or takes one away ({-1}) - and keeps it if it still has one answer,
// is still beyond the techniques, and scores at least nearly as well. Workers share their best finds through the main thread.
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { cpus } from 'node:os'
import { engineFor, seeded } from './engine.js'

const e = engineFor(9)
const SINGLES = new Set(['full_house', 'hidden_single', 'naked_single'])

// ---------------------------------------------------------------- scoring
function propagate(values, cands, singlesOnly) {
  for (let n = 0; n < 2000; n++) {
    if (values.every(Boolean)) return 'solved'
    for (let i = 0; i < 81; i++) if (!values[i] && !cands[i]) return 'bad'
    const s = e.findStep(values, cands)
    if (!s || (singlesOnly && !SINGLES.has(s.technique))) return 'stuck'
    e.apply(values, cands, s)
    if (s.place && e.PEERS[s.place.cell].some((p) => values[p] === s.place.digit)) return 'bad'
  }
  return 'stuck'
}
function chainLength(values, cands) {           // singles from here until a contradiction: how many placements (or null)
  let n = 0
  for (let k = 0; k < 200; k++) {
    for (let i = 0; i < 81; i++) if (!values[i] && !cands[i]) return n
    const s = e.findStep(values, cands)
    if (!s || !SINGLES.has(s.technique)) return null
    e.apply(values, cands, s)
    if (e.PEERS[s.place.cell].some((p) => values[p] === s.place.digit)) return n
    n++
    if (values.every(Boolean)) return null
  }
  return null
}
// one trial with every technique: does assuming (c, d) lead to a contradiction?
function trialFails(values, cands, c, d, depth) {
  const v = [...values], k = [...cands]
  e.apply(v, k, { place: { cell: c, digit: d }, eliminate: [] })
  const r = propagate(v, k, false)
  if (r === 'bad') return true
  if (r === 'stuck' && depth > 1) return solveByTrials(v, k, depth - 1) === 'bad'
  return false
}
function solveByTrials(values, cands, depth) {
  for (let guard = 0; guard < 60; guard++) {
    const r = propagate(values, cands, false)
    if (r !== 'stuck') return r
    let found = false
    for (let c = 0; c < 81 && !found; c++) if (!values[c]) for (const d of e.digitsOf(cands[c])) {
      if (trialFails(values, cands, c, d, depth)) { cands[c] &= ~(1 << (d - 1)); found = true; break }
    }
    if (!found) return 'stuck'
  }
  return 'stuck'
}
export function score(puzzle) {
  const values = [...puzzle], cands = e.candidates(values)
  let worst = 0, useful = 99
  for (let guard = 0; guard < 60; guard++) {
    const r = propagate(values, cands, false)
    if (r === 'solved') break
    if (r === 'bad') return 0
    let best = null, count = 0
    for (let c = 0; c < 81; c++) if (!values[c]) for (const d of e.digitsOf(cands[c])) {
      const v = [...values], k = [...cands]
      e.apply(v, k, { place: { cell: c, digit: d }, eliminate: [] })
      const n = chainLength(v, k)
      if (n != null) { count++; if (!best || n < best.n) best = { n, c, d } }
    }
    if (!best) {                                // no chain of singles cracks this stall: tier 2 or 3
      const tier = solveByTrials([...values], [...cands], 1) === 'solved' ? 2 : 3
      const clues = puzzle.filter(Boolean).length
      return tier * 1000 + (40 - clues) * 5 + Math.min(99, guard * 3)
    }
    worst = Math.max(worst, best.n)
    useful = Math.min(useful, count)
    cands[best.c] &= ~(1 << (best.d - 1))
  }
  const clues = puzzle.filter(Boolean).length
  return 1000 + worst * 10 + Math.max(0, 30 - clues) + Math.max(0, 10 - useful)
}

// ---------------------------------------------------------------- the search
function nudge(p, sol, rand) {
  const q = [...p]
  const filled = q.map((v, i) => (v ? i : -1)).filter((i) => i >= 0)
  const empty = q.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0)
  const pick = (xs, k) => { const a = [...xs], out = []; for (let j = 0; j < k && a.length; j++) out.push(a.splice(Math.floor(rand() * a.length), 1)[0]); return out }
  const r = rand()
  if (r < 0.15) { for (const c of pick(filled, 1)) q[c] = 0; return q }          // {-1}: fewer clues
  const k = r < 0.75 ? 1 : 2                                                      // {-k+k}: distinct cells
  for (const c of pick(filled, k)) q[c] = 0
  for (const c of pick(empty, k)) q[c] = sol[c]
  return q
}

if (isMainThread) {
  const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1]]] : a), []))
  const hours = Number(args.hours ?? 0)
  const threads = Math.max(1, Number(args.threads ?? Math.max(1, cpus().length - 1)))
  const seedFile = args.seeds ?? 'seeds.tsv'
  const read = (f) => readFileSync(f, 'utf8').split(/\r?\n/).filter((l) => /^\d/.test(l)).map((l) => l.split('\t').at(-1).trim()).filter((p) => p.length === 81)
  const seeds = [...new Set([...read(seedFile), ...(existsSync('found.tsv') ? read('found.tsv') : [])])]
  console.log(`Starting: ${threads} threads, ${seeds.length} seed puzzles, ${hours ? `${hours} hours` : 'until stopped (Ctrl+C)'}. Scoring the seeds...`)
  const best = new Map()                       // puzzle text -> score
  const save = () => {
    const rows = [...best.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2000)
    const lines = ['# The sudoku search\'s finds (tools/sudoku-search). Columns: rank, score (1000s = tier), clues, puzzle.', 'rank\tscore\tclues\tpuzzle',
      ...rows.map(([p, s], i) => `${i + 1}\t${s}\t${[...p].filter((c) => c !== '0').length}\t${p}`)]
    writeFileSync('found.tsv', lines.join('\n') + '\n')
    const tiers = {}
    for (const [, s] of rows) tiers[Math.floor(s / 1000)] = (tiers[Math.floor(s / 1000)] ?? 0) + 1
    return { top: rows[0]?.[1], tiers }
  }
  const t0 = Date.now()
  let tried = 0
  const workers = []
  const share = Math.ceil(seeds.length / threads)
  for (let i = 0; i < threads; i++) {
    const w = new Worker(new URL(import.meta.url), { workerData: { seed: Date.now() + i * 7919, seeds: seeds.slice(i * share, (i + 1) * share).concat(seeds.slice(0, 20)) } })
    w.on('message', (m) => {
      tried += m.tried
      for (const [p, s] of m.finds) if (!best.has(p) || best.get(p) < s) best.set(p, s)
      for (const other of workers) if (other !== w) other.postMessage({ share: m.finds.slice(0, 5) })
    })
    w.on('error', (err) => console.error('A worker stopped:', err.message))
    workers.push(w)
  }
  const report = () => {
    const { top, tiers } = save()
    const mins = ((Date.now() - t0) / 60000).toFixed(0)
    console.log(`${new Date().toLocaleTimeString()}  ${mins} min · ${tried.toLocaleString()} tried · best score ${top ?? '-'} · by tier ${JSON.stringify(tiers)} · saved to found.tsv`)
  }
  const timer = setInterval(report, 3 * 60000)
  const stop = () => { clearInterval(timer); report(); console.log('Stopped. Copy found.tsv to the app PC (README.txt).'); process.exit(0) }
  process.on('SIGINT', stop)
  if (hours) setTimeout(stop, hours * 3600000)
} else {
  const rand = seeded(workerData.seed)
  const pool = new Map()
  for (const text of workerData.seeds) { const p = e.parse(text); if (p) pool.set(text, score(p)) }
  parentPort.on('message', (m) => { for (const [p, s] of m.share ?? []) if (!pool.has(p)) pool.set(p, s) })
  let tried = 0, finds = [], last = Date.now()
  const loop = () => {
    for (let n = 0; n < 50; n++) {
      const sorted = [...pool.entries()].sort((a, b) => b[1] - a[1])
      const [text, s0] = sorted[Math.floor(rand() ** 2 * Math.min(80, sorted.length))]
      const p = e.parse(text)
      const sol = e.solve(p)
      const q = nudge(p, sol, rand)
      tried++
      if (e.solveCount(q) !== 1 || e.grade(q).level !== 5) continue
      const kq = e.toText(q)
      if (pool.has(kq)) continue
      const s = score(q)
      if (s >= s0 - 15) {
        pool.set(kq, s)
        if (s >= 1150) finds.push([kq, s])
      }
      if (pool.size > 600) { for (const [w] of [...pool.entries()].sort((a, b) => a[1] - b[1]).slice(0, pool.size - 600)) pool.delete(w) }
    }
    if (Date.now() - last > 60000) {
      const top = [...pool.entries()].sort((a, b) => b[1] - a[1]).slice(0, 40)
      parentPort.postMessage({ tried, finds: [...new Map([...finds, ...top]).entries()] })
      tried = 0
      finds = []
      last = Date.now()
    }
    setImmediate(loop)
  }
  loop()
}
