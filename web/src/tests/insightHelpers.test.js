import { describe, expect, it } from 'vitest'
import { fmtSecs, hasClock, paceBars, skillChange, timeNote, weakestSkill } from '../modules/chess/insightHelpers.js'

describe('fmtSecs', () => {
  it('shows seconds and minutes', () => {
    expect(fmtSecs(8)).toBe('8s')
    expect(fmtSecs(8.5)).toBe('8.5s')
    expect(fmtSecs(62)).toBe('1m 02s')
    expect(fmtSecs(null)).toBe('')
  })
})

describe('timeNote', () => {
  it('says nothing without a clock', () => {
    expect(timeNote({ kind: 'best' })).toBe('')
    expect(hasClock([{ kind: 'best' }])).toBe(false)
  })
  it('flags a bad move made short of time', () => {
    expect(timeNote({ clock: 9, spent: 3, low: true, kind: 'blunder' })).toBe('Took 3s, 9s left - a mistake in time trouble')
    expect(timeNote({ clock: 90, spent: 12, low: false, kind: 'best' })).toBe('Took 12s, 1m 30s left')
  })
})

describe('paceBars', () => {
  it('scales to the long thinks without letting one flatten the rest', () => {
    const moves = [1, 2, 3, 4, 5, 6, 7, 8, 9, 600].map((s, i) => ({ ply: i + 1, colour: 'white', spent: s, kind: 'good' }))
    const bars = paceBars(moves)
    expect(bars[9].h).toBe(100)
    expect(bars[8].h).toBe(100)           // the 90th percentile is the cap
    expect(bars[0].h).toBeLessThan(20)
    expect(paceBars([{ ply: 1, kind: 'best' }])).toEqual([])
  })
})

describe('skills', () => {
  it('compares lately with before', () => {
    expect(skillChange({ recent: 80, before: 70 })).toEqual({ text: 'up 10 on before', tone: 'up' })
    expect(skillChange({ recent: 60, before: 70 }).tone).toBe('down')
    expect(skillChange({ recent: 71, before: 70 }).tone).toBe('same')
    expect(skillChange({ recent: 71, before: null }).text).toBe('')
  })
  it('finds the weakest one that has a score', () => {
    expect(weakestSkill([{ id: 'a', score: 80 }, { id: 'b', score: 40 }, { id: 'c', score: null }]).id).toBe('b')
    expect(weakestSkill([{ id: 'c', score: null }])).toBeNull()
  })
})
