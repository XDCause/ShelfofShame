import { describe, expect, it } from 'vitest'
import { gapLabel, hoursMinutes, splitTally, steepestStretch } from '../modules/hiking/hikingMath.js'

// A track going north: a point every 100 m, [lat, lon, ele, seconds, metres along].
const track = (heights) => heights.map((e, i) => [0, 0, e, i * 60, i * 100])

describe('steepestStretch', () => {
  it('finds the steepest 500 m climb', () => {
    // flat, then 5 steps of +10 m (a 10% climb for 500 m), then flat
    const s = steepestStretch(track([100, 100, 100, 110, 120, 130, 140, 150, 150, 150]))
    expect(s.fromM).toBe(200)
    expect(s.toM).toBe(700)
    expect(s.gain).toBe(50)
    expect(s.grade).toBeCloseTo(0.1)
    expect(s.seconds).toBe(300)
  })
  it('is null for a short, flat or downhill track', () => {
    expect(steepestStretch(track([100, 110, 120]))).toBeNull()
    expect(steepestStretch(track([100, 100, 100, 100, 100, 100, 100]))).toBeNull()
    expect(steepestStretch(track([160, 150, 140, 130, 120, 110, 100]))).toBeNull()
    expect(steepestStretch(null)).toBeNull()
  })
  it('works without times', () => {
    const t = track([0, 10, 20, 30, 40, 50, 60]).map((p) => [p[0], p[1], p[2], null, p[4]])
    expect(steepestStretch(t).seconds).toBeNull()
  })
})

describe('hoursMinutes', () => {
  it('reads as hours and minutes', () => {
    expect(hoursMinutes(3900)).toBe('1 h 05 min')
    expect(hoursMinutes(1500)).toBe('25 min')
    expect(hoursMinutes(null)).toBe('—')
  })
})

describe('gapLabel and splitTally', () => {
  it('writes a signed minutes:seconds gap', () => {
    expect(gapLabel(80)).toBe('+1:20')
    expect(gapLabel(-5)).toBe('-0:05')
    expect(gapLabel(0)).toBe('same')
    expect(gapLabel(null)).toBe('—')
  })
  it('counts the kilometres against the best run', () => {
    expect(splitTally([{ gap_s: -10 }, { gap_s: 20 }, { gap_s: 0 }, { gap_s: 5 }])).toEqual({ quicker: 1, slower: 2, level: 1 })
    expect(splitTally(undefined)).toEqual({ quicker: 0, slower: 0, level: 0 })
  })
})
