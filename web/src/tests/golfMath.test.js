import { describe, expect, it } from 'vitest'
import { BLANK, centre, changeHole, enqueue, failure, flat, greenDistances, holeFrame, metresBetween, ring, roundTotals,
  scoreKind, stableford, shotDistances, suggestClub, toParText } from '../modules/golf/golfMath.js'

// Brisbane-ish. A metre north is 1 / 111195 of a degree of latitude.
const LAT = -27.5
const LON = 153.0
const N = 1 / 111195
const E = 1 / (111195 * Math.cos((LAT * Math.PI) / 180))
const at = (north, east) => [LAT + north * N, LON + east * E]
// A 20 m square green whose middle is 150 m north of the origin (corners closed, as OpenStreetMap gives them).
const square = [at(140, -10), at(140, 10), at(160, 10), at(160, -10), at(140, -10)]

describe('metresBetween and flat', () => {
  it('measures metres', () => {
    expect(metresBetween(at(0, 0), at(100, 0))).toBeCloseTo(100, 0)
    expect(metresBetween(at(0, 0), at(0, 100))).toBeCloseTo(100, 0)
    expect(metresBetween(at(0, 0), at(30, 40))).toBeCloseTo(50, 0)
  })
  it('flattens and comes back', () => {
    const f = flat(at(0, 0))
    const [x, y] = f.to(at(30, 40))
    expect(x).toBeCloseTo(40, 0)
    expect(y).toBeCloseTo(30, 0)
    const back = f.from([x, y])
    expect(back[0]).toBeCloseTo(at(30, 40)[0], 9)
    expect(back[1]).toBeCloseTo(at(30, 40)[1], 9)
  })
  it('finds a shape middle, leaving out the closing corner', () => {
    expect(ring(square)).toHaveLength(4)
    const c = centre(square)
    expect(metresBetween(c, at(150, 0))).toBeLessThan(0.01)
    expect(centre([])).toBeNull()
  })
})

describe('greenDistances', () => {
  it('gives front, middle and back along the line through the middle', () => {
    const d = greenDistances(at(0, 0), square)
    expect(d.middle).toBeCloseTo(150, 0)
    expect(d.front).toBeCloseTo(140, 0)
    expect(d.back).toBeCloseTo(160, 0)
  })
  it('works from an angle (the line crosses the corners diagonally)', () => {
    // from 100 m south-west of the middle along the diagonal: the green's corners are 10 * sqrt(2) either side
    const d = greenDistances(at(150 - 100 / Math.SQRT2, -100 / Math.SQRT2), square)
    expect(d.middle).toBeCloseTo(100, 0)
    expect(d.front).toBeCloseTo(100 - 10 * Math.SQRT2, 0)
    expect(d.back).toBeCloseTo(100 + 10 * Math.SQRT2, 0)
  })
  it('says front 0 when you are on the green', () => {
    const d = greenDistances(at(145, 0), square)
    expect(d.front).toBe(0)
    expect(d.middle).toBeCloseTo(5, 0)
    expect(d.back).toBeCloseTo(15, 0)
  })
  it('is null without a green or a position', () => {
    expect(greenDistances(at(0, 0), null)).toBeNull()
    expect(greenDistances(null, square)).toBeNull()
    expect(greenDistances(at(0, 0), [at(1, 1), at(2, 2)])).toBeNull()
  })
})

describe('holeFrame', () => {
  it('turns the hole so the green is straight up from the tee', () => {
    // a hole running east: tee at the origin, green 300 m east
    const green = [at(-10, 290), at(-10, 310), at(10, 310), at(10, 290)]
    const f = holeFrame({ line: [at(0, 0), at(0, 300)], green })
    expect(f.bearing).toBeCloseTo(90, 0)
    const [tx, ty] = f.toXY(at(0, 0))
    const [gx, gy] = f.toXY(at(0, 300))
    expect(tx).toBeCloseTo(0, 3)
    expect(ty).toBeCloseTo(0, 3)
    expect(gx).toBeCloseTo(0, 0)
    expect(gy).toBeCloseTo(-300, 0)               // up the screen (SVG y grows down)
    // a point right of the line (south of an eastward hole) is drawn to the right
    expect(f.toXY(at(-20, 150))[0]).toBeCloseTo(20, 0)
    // and back again (the tap measure)
    const back = f.fromXY(f.toXY(at(-20, 150)))
    expect(metresBetween(back, at(-20, 150))).toBeLessThan(0.01)
    // the box holds the tee and the green, padded, and isn't a thin strip
    expect(f.box.y).toBeLessThan(-300)
    expect(f.box.y + f.box.h).toBeGreaterThan(0)
    expect(f.box.w).toBeGreaterThanOrEqual(f.box.h * 0.5 - 0.01)
  })
  it('is null for a hole without a map', () => {
    expect(holeFrame(null)).toBeNull()
    expect(holeFrame({ line: null, green: null, tees: [] })).toBeNull()
  })
})

describe('scoring', () => {
  it('counts Stableford points like the API', () => {
    expect(stableford(4, 4, 0)).toBe(2)
    expect(stableford(5, 4, 1)).toBe(2)
    expect(stableford(3, 4, 1)).toBe(4)
    expect(stableford(8, 4, 0)).toBe(0)
    expect(stableford(null, 4, 2)).toBe(0)
  })
  it('names a score', () => {
    expect(scoreKind(2, 4)).toBe('eagle')
    expect(scoreKind(3, 4)).toBe('birdie')
    expect(scoreKind(4, 4)).toBe('par')
    expect(scoreKind(5, 4)).toBe('bogey')
    expect(scoreKind(9, 4)).toBe('double')
    expect(scoreKind(null, 4, true)).toBe('double')
    expect(scoreKind(null, 4)).toBeNull()
    expect(toParText(0)).toBe('E')
    expect(toParText(3)).toBe('+3')
    expect(toParText(-2)).toBe('−2')
  })
  it('starts strokes at par and putts at 2', () => {
    expect(changeHole(BLANK, 4, { strokes: 1 }).strokes).toBe(4)
    expect(changeHole(BLANK, 5, { strokes: -1 }).strokes).toBe(5)
    expect(changeHole(BLANK, 4, { putts: 1 }).putts).toBe(2)
    expect(changeHole(BLANK, 4, { putts: -1 }).putts).toBe(1)
  })
  it('keeps putts and penalties within the strokes', () => {
    let s = changeHole(BLANK, 3, { strokes: 1 })                 // 3
    s = changeHole(s, 3, { putts: 1 })                           // 2 putts
    s = changeHole(s, 3, { penalties: 1 })                       // + a penalty: 3 used of 3
    s = changeHole(s, 3, { putts: 1 })                           // a third putt lifts the strokes to 4
    expect(s).toMatchObject({ strokes: 4, putts: 3, penalties: 1 })
    s = changeHole(s, 3, { strokes: -1 })                        // strokes down: the putts give way
    expect(s).toMatchObject({ strokes: 3, putts: 2, penalties: 1 })
  })
  it('toggles fairway and first putt, picks up and clears', () => {
    let s = changeHole(BLANK, 4, { fairway: 'hit' })
    expect(s.fairway).toBe('hit')
    expect(changeHole(s, 4, { fairway: 'hit' }).fairway).toBeNull()
    s = changeHole(changeHole(s, 4, { putts: 1 }), 4, { first_putt_m: 3 })
    expect(s.first_putt_m).toBe(3)
    expect(changeHole(s, 4, { putts: -1 }).putts).toBe(1)
    s = changeHole(changeHole(s, 4, { strokes: 1 }), 4, { picked_up: true })
    expect(s).toMatchObject({ picked_up: true, strokes: null })
    s = changeHole(s, 4, { strokes: 1 })
    expect(s).toMatchObject({ picked_up: false, strokes: 4 })
    expect(changeHole(s, 4, { clear: true })).toEqual(BLANK)
  })
  it('adds up the round from this device', () => {
    const holes = [{ hole_no: 1, par: 4, received: 1 }, { hole_no: 2, par: 3, received: 0 }, { hole_no: 3, par: 5, received: 1 }]
    const t = roundTotals(holes, { 1: { ...BLANK, strokes: 5 }, 2: { ...BLANK, picked_up: true } })
    expect(t).toEqual({ played: 2, of: 3, strokes: 5, points: 2, toPar: 1 })
    expect(roundTotals(holes, {}).toPar).toBeNull()
  })
})

describe('shots and clubs', () => {
  const bag = [{ club_id: 1, name: 'Driver', carry_m: 220, kind: 'driver' }, { club_id: 2, name: '7 iron', carry_m: 140, kind: 'iron' },
    { club_id: 3, name: 'PW', carry_m: 100, kind: 'wedge' }, { club_id: 4, name: 'Putter', kind: 'putter' },
    { club_id: 5, name: 'Old 3 wood', carry_m: 190, kind: 'wood', in_bag: false }]
  it('suggests the club whose carry is nearest', () => {
    expect(suggestClub(bag, 150).club_id).toBe(2)
    expect(suggestClub(bag, 190).club_id).toBe(1)      // (the 3 wood's out of the bag)
    expect(suggestClub(bag, 20).club_id).toBe(3)
    expect(suggestClub(bag, null)).toBeNull()
    expect(suggestClub([], 100)).toBeNull()
  })
  it('measures each shot to the next', () => {
    const d = shotDistances([{ seq: 1, lat: at(0, 0)[0], lon: at(0, 0)[1] }, { seq: 2, lat: at(200, 0)[0], lon: at(200, 0)[1] }])
    expect(d[0].metres).toBe(200)
    expect(d[1].metres).toBeNull()
  })
})

describe('the waiting list', () => {
  it("keeps one score per hole but every shot in order", () => {
    let q = []
    q = enqueue(q, { n: 'a', kind: 'hole', hole: 1, data: { strokes: 4 } })
    q = enqueue(q, { n: 'b', kind: 'shot', hole: 2, seq: 1 })
    q = enqueue(q, { n: 'c', kind: 'hole', hole: 1, data: { strokes: 5 } })
    q = enqueue(q, { n: 'd', kind: 'unshot', hole: 2, seq: 1 })
    expect(q.map((x) => x.n)).toEqual(['b', 'c', 'd'])
  })
  it('retries what signal would fix, drops what the server refused', () => {
    expect(failure(new TypeError('Failed to fetch'))).toBe('retry')
    expect(failure({ status: 503 })).toBe('retry')
    expect(failure({ status: 401 })).toBe('retry')
    expect(failure({ status: 422 })).toBe('drop')
    expect(failure({ status: 404 })).toBe('drop')
  })
})
