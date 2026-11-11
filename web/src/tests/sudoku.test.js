// The Sudoku engine: puzzles with one answer, steps that never contradict it, the daily puzzle the same each day,
// techniques found where they apply, and hints that point out a mistake first.
import { describe, expect, it } from 'vitest'
import { ALL, apply, bit, candidates, engineFor, findStep, generate, grade, hintFor, makePuzzle, parse, seeded, solve, solveCount, toText } from '../modules/sudoku/engine.js'

const engineFor9 = () => engineFor(9)

const WIKI = parse('530070000600195000098000060800060003400803001700020006060000280000419005000080079')
const WIKI_ANSWER = parse('534678912672195348198342567859761423426853791713924856961537284287419635345286179')

describe('the engine', () => {
  it('reads a grid and finds its one answer', () => {
    expect(parse('5300700006001950000980000600800060003400803001700020006060000280000419005000080079')).toBe(null)   // 82 digits
    expect(parse('53..7....' + '0'.repeat(72))[2]).toBe(0)
    expect(solveCount(WIKI)).toBe(1)
    expect(toText(solve(WIKI))).toBe(toText(WIKI_ANSWER))
    const twoRowsBlank = [...new Array(18).fill(0), ...WIKI_ANSWER.slice(18)]
    expect(solveCount(twoRowsBlank)).toBe(2)
    expect(solveCount([5, 5, ...new Array(79).fill(0)])).toBe(0)
  })

  it('grades a puzzle by solving it like a person', () => {
    const g = grade(WIKI)
    expect(g.level).toBe(1)
    expect(g.logical).toBe(true)
    expect(g.clues).toBe(30)
    expect(g.difficulty).toBe('Medium')                    // singles only, but under 34 clues
  })

  it('makes puzzles with one answer, and never takes a wrong step', () => {
    const rand = seeded(2026)
    for (let i = 0; i < 25; i++) {
      const { puzzle, solution } = makePuzzle(rand)
      expect(solveCount(puzzle)).toBe(1)
      const values = [...puzzle]
      const cands = candidates(values)
      for (let s = findStep(values, cands); s; s = findStep(values, cands)) {
        if (s.place) expect(solution[s.place.cell]).toBe(s.place.digit)
        for (const e of s.eliminate) expect(solution[e.cell]).not.toBe(e.digit)
        apply(values, cands, s)
        if (values.every(Boolean)) break
      }
    }
  })

  it('makes the same daily puzzle from the same seed, at the difficulty asked', () => {
    const a = generate(seeded(77), { difficulty: 'Hard' })
    const b = generate(seeded(77), { difficulty: 'Hard' })
    expect(toText(a.puzzle)).toBe(toText(b.puzzle))
    expect(a.grade.difficulty).toBe('Hard')
    const easy = generate(seeded(5), { difficulty: 'Easy' })
    expect(easy.grade.clues).toBeGreaterThanOrEqual(34)
  })
})

describe('techniques', () => {
  it('finds an X-Wing', () => {
    const values = new Array(81).fill(0)
    const cands = new Array(81).fill(ALL)
    for (const r of [0, 4]) for (let c = 0; c < 9; c++) if (c !== 1 && c !== 7) cands[r * 9 + c] &= ~bit(5)
    const s = findStep(values, cands, 'x_wing')
    expect(s.technique).toBe('x_wing')
    expect(s.cells).toEqual([1, 7, 37, 43])
    const gone = s.eliminate.map((e) => e.cell)
    expect(gone).toContain(2 * 9 + 1)                        // r3c2
    expect(gone).not.toContain(1)
    expect(s.eliminate.every((e) => e.digit === 5)).toBe(true)
  })

  it('finds an XY-Wing', () => {
    const values = new Array(81).fill(0)
    const cands = new Array(81).fill(ALL)
    cands[0] = bit(1) | bit(2)                                // pivot r1c1
    cands[4] = bit(1) | bit(3)                                // r1c5 (same row)
    cands[36] = bit(2) | bit(3)                               // r5c1 (same column)
    const s = findStep(values, cands, 'xy_wing')
    expect(s.technique).toBe('xy_wing')
    expect(s.eliminate).toContainEqual({ cell: 40, digit: 3 })   // r5c5 sees both wings
    expect(s.text).toMatch(/can't be 3/)
  })
})

describe('hints', () => {
  it('point out a wrong digit first, then a step', () => {
    const values = [...WIKI]
    values[2] = 9                                             // the answer there is 4
    expect(hintFor(values, new Array(81).fill(0), WIKI_ANSWER).technique).toBe('mistake')
    const h = hintFor([...WIKI], new Array(81).fill(0), WIKI_ANSWER)
    expect(['full_house', 'hidden_single', 'naked_single']).toContain(h.technique)
    expect(WIKI_ANSWER[h.place.cell]).toBe(h.place.digit)
  })

  it('notice notes that leave out the answer', () => {
    const notes = new Array(81).fill(0)
    notes[2] = bit(1) | bit(2)                                // r1c3's answer is 4
    expect(hintFor([...WIKI], notes, WIKI_ANSWER).technique).toBe('note_mistake')
  })
})

describe('the 16 x 16 giant', () => {
  it('makes and checks a 16 x 16 with the digits 1-9 then A-G', async () => {
    const { engineFor, sym } = await import('../modules/sudoku/engine.js')
    const e = engineFor(16)
    expect(e.CELLS).toBe(256)
    expect(e.BOXES[1][4]).toBe(16 + 4)                       // box 2's fifth cell: row 2, column 5
    const made = e.generate(seeded(16), { difficulty: 'Easy' })
    expect(made.grade.difficulty).toBe('Easy')
    expect(e.solveCount(made.puzzle)).toBe(1)
    const text = e.toText(made.puzzle)
    expect(text).toMatch(/^[0-9A-G]{256}$/)
    expect(e.toText(e.parse(text))).toBe(text)
    expect(sym(16)).toBe('G')
    const h = e.hintFor([...made.puzzle], new Array(256).fill(0), made.solution)
    expect(made.solution[h.place.cell]).toBe(h.place.digit)
  })
})

describe('practice', () => {
  it('starts at the moment the technique is the next move', () => {
    const made = generate(seeded(11), { technique: 'x_wing' })
    const { practiceStart } = engineFor9()
    const start = practiceStart(made.puzzle, 'x_wing')
    expect(start.step.technique).toBe('x_wing')
    expect(start.values.filter(Boolean).length).toBeGreaterThan(made.puzzle.filter(Boolean).length)   // easier steps done
    start.values.forEach((v, i) => { if (v) expect(v).toBe(made.solution[i]) })
    expect(hintFor(start.values, start.cands, made.solution).technique).toBe('x_wing')                // the lesson's step
  })
})

describe('the Hardest 100 and events', () => {
  it('has 100 different puzzles, each with one answer and beyond the techniques', async () => {
    const { HARDEST } = await import('../modules/sudoku/hardest.js')
    expect(HARDEST).toHaveLength(100)
    expect(new Set(HARDEST).size).toBe(100)
    for (const text of HARDEST.slice(0, 10).concat(HARDEST.slice(-10))) {
      const p = parse(text)
      expect(solveCount(p)).toBe(1)
      expect(grade(p).level).toBe(5)
    }
  })

  it("lays out each event's path, with its rewards", async () => {
    const { EVENTS, stops, earnedThemes, eventOpen } = await import('../modules/sudoku/events.js')
    const tour = EVENTS.find((e) => e.key === 'grand-tour')
    const path = stops(tour)
    expect(path).toHaveLength(30)
    expect(path[0]).toMatchObject({ stop: 1, difficulty: 'Easy', size: 9 })
    expect(path[14]).toMatchObject({ size: 16, difficulty: 'Medium' })
    expect(path[29].difficulty).toBe('Extreme')
    expect([...earnedThemes({ 'grand-tour': { furthest: 12 }, hardest: { solved: 10 } })].sort()).toEqual(['classic', 'forest', 'obsidian', 'paper'])
    expect(eventOpen(EVENTS[1], '2026-11-11')).toBe(false)
    expect(eventOpen(EVENTS[1], '2026-12-25')).toBe(true)
  })
})

describe('Diagonal (X), Advent and photos', () => {
  it('makes Diagonal (X) puzzles whose diagonals hold every digit', () => {
    const x = engineFor(9, 'x')
    const made = x.generate(seeded(3), { difficulty: 'Easy' })
    for (const diag of x.DIAGS) expect(new Set(diag.map((c) => made.solution[c])).size).toBe(9)
    expect(x.solveCount(made.puzzle)).toBe(1)
    expect(made.grade.variant).toBe('x')
    expect(x.unitName(27)).toBe('the ↘ diagonal')
  })

  it('opens an Advent door on its day', async () => {
    const { advent, stops } = await import('../modules/sudoku/events.js')
    const a = advent(2026)
    expect(a.key).toBe('advent-2026')
    expect(a.opens(5)).toBe('2026-12-05')
    expect(stops(a)[23].difficulty).toBe('Extreme')
  })

  it('maps a photo\'s four corners onto a square', async () => {
    const { homography, applyH } = await import('../modules/sudoku/photoRead.js')
    const corners = [[40, 30], [420, 50], [430, 460], [20, 440]]
    const H = homography([[0, 0], [450, 0], [450, 450], [0, 450]], corners)
    const [x, y] = applyH(H, 450, 450)
    expect(x).toBeCloseTo(430, 6)
    expect(y).toBeCloseTo(460, 6)
    const [mx, my] = applyH(H, 0, 450)
    expect(mx).toBeCloseTo(20, 6)
    expect(my).toBeCloseTo(440, 6)
  })
})

describe('the weekly', () => {
  it('only has hard ones: at most 30 clues, beyond the techniques (one with 44 clues got in once - solved in 3 minutes)', async () => {
    const { WEEKLY } = await import('../modules/sudoku/weekly.js')
    expect(WEEKLY.length).toBeGreaterThan(300)
    for (const text of WEEKLY) expect(parse(text).filter(Boolean).length).toBeLessThanOrEqual(30)
    for (const text of WEEKLY.slice(0, 15)) expect(grade(parse(text)).level).toBe(5)
  })
})
