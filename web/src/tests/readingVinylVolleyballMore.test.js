import { describe, expect, it } from 'vitest'
import { changeText, lastCleaned, loanTime, stylusText } from '../modules/vinyl/vinylMoreHelpers.js'
import { clipFilterName, nextRotation, percentText, resultText, trendText } from '../modules/volleyball/vbHelpers.js'

describe('vinyl helpers', () => {
  it('words a value change', () => {
    expect(changeText({ days: 30, change: 12.5, percent: 2.1 })).toBe('+$12.50 (+2.1%) in the last month')
    expect(changeText({ days: 365, change: -3, percent: -1 })).toBe('−$3.00 (−1%) in the last year')
    expect(changeText({ days: 7, change: 1, percent: null })).toBe('+$1.00 in the last 7 days')
  })
  it('words the stylus', () => {
    expect(stylusText({ hours: 100, limit_hours: 800, hours_left: 700 })).toBe('100 of 800 hours - 700 hours left')
    expect(stylusText({ hours: 750, limit_hours: 800, hours_left: 50, soon: true })).toMatch(/order a new one/)
    expect(stylusText({ hours: 810, limit_hours: 800, hours_left: -10, due: true })).toMatch(/time to replace/)
  })
  it('words a loan and the last cleaning', () => {
    expect([0, 1, 5, 20].map(loanTime)).toEqual(['today', '1 day', '5 days', '2 weeks'])
    expect(lastCleaned([])).toBeNull()
    expect(lastCleaned([{ kind: 'clean', done_on: '2026-01-02' }, { kind: 'clean', done_on: '2026-03-04' }])).toBe('2026-03-04')
  })
})

describe('volleyball helpers', () => {
  it('words a trend', () => {
    expect(trendText(null)).toMatch(/Not enough/)
    expect(trendText(0.02)).toBe('Steady')
    expect(trendText(0.34)).toBe('Up 0.3 on the games before')
    expect(trendText(-0.5)).toBe('Down 0.5 on the games before')
  })
  it('rotates after a side-out only', () => {
    expect(nextRotation(1, false, true)).toBe(2)
    expect(nextRotation(6, false, true)).toBe(1)
    expect(nextRotation(3, true, true)).toBe(3)
    expect(nextRotation(3, false, false)).toBe(3)
  })
  it('names clip filters', () => {
    expect(clipFilterName('serve', 'error')).toBe('Serve errors')
    expect(clipFilterName('dig', 'good')).toBe('Good digs')
    expect(clipFilterName('block', '')).toBe('Blocks')
    expect(clipFilterName('', 'error')).toBe('Errors')
    expect(clipFilterName('', '')).toBe('All clips')
  })
  it('shows results and percents', () => {
    expect(percentText(null)).toBe('–')
    expect(percentText(75)).toBe('75%')
    expect(resultText(14, 'in a row')).toBe('14 in a row')
    expect(resultText(null)).toBe('–')
  })
})
