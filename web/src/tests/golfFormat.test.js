import { describe, expect, it } from 'vitest'
import { hcpText, holeSketch, oneADay, parsePars, sgRows, toPar, weakest } from '../modules/golf/golfFormat.js'

describe('golf formats', () => {
  it('reads a score against par and a handicap', () => {
    expect(toPar(0)).toBe('E')
    expect(toPar(7)).toBe('+7')
    expect(toPar(-2)).toBe('−2')
    expect(toPar(null)).toBe('—')
    expect(hcpText(18.4)).toBe('18.4')
    expect(hcpText('12')).toBe('12.0')
    expect(hcpText(-1.2)).toBe('+1.2')          // a plus handicap
    expect(hcpText(null)).toBe('—')
  })

  it('finds the part of your game furthest behind', () => {
    expect(weakest({ fairways: 12, gir: 22.5, putts: 8 })).toBe('gir')
    expect(weakest({ putts: 8 })).toBe(null)      // nothing to compare with
    expect(weakest(null)).toBe(null)
  })

  it('keeps only strokes-gained categories with holes', () => {
    const rows = sgRows({ off_tee: { holes: 0, per18: null }, approach: { holes: 9, per18: -4.2 }, putting: { holes: 18, per18: -1 } })
    expect(rows.map((r) => r.key)).toEqual(['approach', 'putting'])
  })

  it('keeps one point a day for a line chart', () => {
    expect(oneADay([{ x: '2026-01-01', y: 1 }, { x: '2026-01-01', y: 2 }, { x: '2026-01-02', y: 3 }]))
      .toEqual([{ x: '2026-01-01', y: 2 }, { x: '2026-01-02', y: 3 }])
  })

  it('reads typed pars', () => {
    expect(parsePars('4 4 3, 5 4 4 3 4 5', 9)).toEqual([4, 4, 3, 5, 4, 4, 3, 4, 5])
    expect(parsePars('', 18)).toEqual([])
    expect(parsePars('4 4 3', 9)).toBe(null)
    expect(parsePars('4 4 3 5 4 4 3 4 9', 9)).toBe(null)
  })

  it('turns a hole so the tee is at the bottom and the green at the top', () => {
    // a hole running east: 300 m
    const east = 300 / (111320 * Math.cos((-27.45 * Math.PI) / 180))
    const s = holeSketch({ line: [[-27.45, 153.0], [-27.45, 153.0 + east]], green: [[-27.45, 153.0 + east], [-27.4501, 153.0 + east]], tees: [], fairways: [], bunkers: [], water: [] })
    const pts = s.line.slice(1).split('L').map((p) => p.split(' ').map(Number))
    expect(pts[0][0]).toBeCloseTo(0, 0)
    expect(pts[0][1]).toBeCloseTo(0, 0)
    expect(pts[1][0]).toBeCloseTo(0, 0)            // straight up...
    expect(pts[1][1]).toBeCloseTo(-300, 0)         // ...300 m
    expect(s.green.endsWith('Z')).toBe(true)
    expect(s.width).toBeGreaterThanOrEqual(70)
    expect(holeSketch({ line: [[0, 0]] })).toBe(null)
    expect(holeSketch(null)).toBe(null)
  })
})
