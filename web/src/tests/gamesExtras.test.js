import { describe, expect, it } from 'vitest'
import { easiestLocked, estimateText, moneyText, perHourText, pickDetail } from '../modules/videogames/backlogHelpers.js'
import { addTag, gridOut, overLimit, roundTotals, tagSuggestions, turnClocks, turnLine, withGrid } from '../modules/boardgames/turnHelpers.js'

describe('turn timer helpers', () => {
  const turns = { running: true, since: '2026-11-15T09:00:00Z', current: 7, cur_s: 10, totals: { 7: 100, 8: 50 }, limit: 60 }
  it('adds the running turn to the current player and to the turn', () => {
    const c = turnClocks(turns, '2026-11-15T09:00:30Z', 5)
    expect(c.current).toBe(45)
    expect(c.totals).toEqual({ 7: 135, 8: 50 })
  })
  it('does not run while paused', () => {
    expect(turnClocks({ ...turns, running: false }, '2026-11-15T09:05:00Z', 5).current).toBe(10)
    expect(turnClocks(null, 'x').totals).toEqual({})
  })
  it('knows when a turn is over the limit', () => {
    expect(overLimit(turns, 61)).toBe(true)
    expect(overLimit(turns, 60)).toBe(false)
    expect(overLimit({ ...turns, limit: null }, 999)).toBe(false)
  })
  it('describes a saved turn time', () => {
    const t = (n) => `${n}s`
    expect(turnLine({ turn_seconds: 120, turn_count: 4, turn_over: 1 }, t)).toBe('120s over 4 turns (avg 30s), 1 over the limit')
    expect(turnLine({ turn_seconds: null }, t)).toBeNull()
  })
})

describe('round grid helpers', () => {
  const rows = [{ 1: '4', 2: 6 }, { 1: 8 }, { 2: '' }]
  it('totals each column and leaves empty ones null', () => {
    expect(roundTotals(rows, [1, 2, 3])).toEqual({ 1: 12, 2: 6, 3: null })
  })
  it('gives a seat with no score its grid total, and keeps one that has a score', () => {
    const seats = [{ player_id: 1, adds: [] }, { player_id: 2, score: 3, adds: [] }, { player_id: 3, adds: [1] }]
    expect(withGrid(seats, rows).map((s) => s.score)).toEqual([12, 3, undefined])
    expect(withGrid(seats, [])).toBe(seats)
  })
  it('sends numbers only', () => {
    expect(gridOut(rows)).toEqual([{ 1: 4, 2: 6 }, { 1: 8 }, {}])
  })
})

describe('tags', () => {
  it('adds a tag once, any case, tidy', () => {
    expect(addTag(['Close game'], '  close   game ')).toEqual(['Close game'])
    expect(addTag(['a'], ' won  late ')).toEqual(['a', 'won late'])
    expect(addTag(['a'], '   ')).toEqual(['a'])
  })
  it('suggests tags used before that match and are not on the play', () => {
    const known = [{ tag: 'close game', plays: 3 }, { tag: 'first time', plays: 2 }, { tag: 'teach', plays: 1 }]
    expect(tagSuggestions(known, ['Teach'], '')).toEqual(['close game', 'first time'])
    expect(tagSuggestions(known, [], 'fir')).toEqual(['first time'])
  })
})

describe('time to beat, easiest achievement and cost', () => {
  it('says where the estimate came from', () => {
    expect(estimateText({ estimate_minutes: 750, estimate_source: 'yours' })).toBe('12.5 h (your estimate)')
    expect(estimateText({ estimate_minutes: 40, estimate_source: 'median' })).toBe('40 min (median of the games you finished)')
    expect(estimateText({ estimate_minutes: null })).toBeNull()
    expect(pickDetail({ estimate_minutes: 600, estimate_source: 'yours', sh_median_minutes: 300 }, 100)).toBe('about 10 h (your estimate)')
  })
  it('finds the unearned achievement most players have', () => {
    const list = [
      { name: 'A', achieved: true, global_percent: 90 },
      { name: 'B', achieved: false, global_percent: 12 },
      { name: 'C', achieved: false, global_percent: 40, unobtainable: true },
      { name: 'D', achieved: false, global_percent: 30 },
      { name: 'E', achieved: false, global_percent: null },
    ]
    expect(easiestLocked(list).name).toBe('D')
    expect(easiestLocked([])).toBeNull()
  })
  it('writes money and cost per hour', () => {
    expect(perHourText(0.6)).toBe('$0.60/h')
    expect(perHourText(null)).toBe('not played yet')
    expect(moneyText(1234.5)).toMatch(/1,?234\.50$/)
  })
})
