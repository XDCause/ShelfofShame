import { describe, expect, it } from 'vitest'
import { dueText, field, gasName, hoursText, metres, minutesText, noFlyLeft, oneADay, stars, tagsFromText } from '../modules/scuba/scubaFormat.js'

describe('scuba formats', () => {
  it('reads depths, times and the gas', () => {
    expect(metres(18.4)).toBe('18.4 m')
    expect(metres(30)).toBe('30 m')
    expect(metres(null)).toBe('—')
    expect(minutesText(45)).toBe('45 min')
    expect(minutesText(85)).toBe('1 h 25 min')
    expect(minutesText(120)).toBe('2 h')
    expect(hoursText(5025)).toBe('83.8 h')
    expect(gasName(21)).toBe('Air')
    expect(gasName(32)).toBe('EAN32')
    expect(gasName(100)).toBe('Oxygen')
    expect(stars(4)).toBe('★★★★☆')
  })

  it('cleans tags and reads a figure that may be a number or an object', () => {
    expect(tagsFromText('Night, wreck;  night ,,Drift')).toEqual(['night', 'wreck', 'drift'])
    expect(tagsFromText('')).toEqual([])
    expect(field(12, 'dives')).toBe(12)
    expect(field({ dives: 3 }, 'dives')).toBe(3)
  })

  it('counts down the no-fly time and clears it when it has passed', () => {
    const now = new Date('2026-11-18T10:00:00').getTime()
    expect(noFlyLeft(null, now)).toEqual({ clear: true })
    expect(noFlyLeft('2026-11-18T09:00:00', now)).toEqual({ clear: true })
    const left = noFlyLeft('2026-11-18T15:12:00', now)
    expect(left.clear).toBe(false)
    expect(left.text).toBe('5 h 12 min')
  })

  it('says when something is due', () => {
    const now = new Date('2026-11-18T10:00:00')
    expect(dueText('2026-11-18', now)).toBe('due today')
    expect(dueText('2026-11-30', now)).toBe('due in 12 days')
    expect(dueText('2026-11-17', now)).toBe('overdue by 1 day')
  })

  it('keeps one point a day for a line chart', () => {
    expect(oneADay([{ x: 'a', y: 1 }, { x: 'a', y: 2 }, { x: 'b', y: 3 }])).toEqual([{ x: 'a', y: 2 }, { x: 'b', y: 3 }])
  })
})
