// The small formatters every page uses (api.js) and the colour families behind the colour filter (supplyExtras.jsx).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { dayDate, duration, isoDay, money, shortDate, timeAgo } from '../api.js'
import { colourKey, familyOf } from '../components/supplyExtras.jsx'

describe('money and durations', () => {
  it('shows dollars the Australian way, and nothing for nothing', () => {
    expect(money(1234.5)).toBe('$1,234.50')
    expect(money('3.95')).toBe('$3.95')
    expect(money(0)).toBe('$0.00')
    expect(money(null)).toBe('')
    expect(money('')).toBe('')
  })
  it('says minutes as hours and minutes', () => {
    expect(duration(45)).toBe('45 min')
    expect(duration(60)).toBe('1 h')
    expect(duration(135)).toBe('2 h 15 min')
    expect(duration(-5)).toBe('0 min')
    expect(duration(null)).toBe('0 min')
  })
})

describe('dates', () => {
  afterEach(() => vi.useRealTimers())
  it('turns a day into words and back', () => {
    expect(shortDate('2026-10-21')).toBe('21 Oct 2026')
    expect(shortDate('')).toBe('')
    expect(isoDay(dayDate('2026-02-28'))).toBe('2026-02-28')
    expect(dayDate('2026-10-21').getHours()).toBe(12)          // (midday: a day never slips across midnight)
  })
  it('says how long ago', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-21T12:00:00'))
    expect(timeAgo('2026-10-21T11:59:40')).toBe('just now')
    expect(timeAgo('2026-10-21T11:15:00')).toBe('45 min ago')
    expect(timeAgo('2026-10-21T09:00:00')).toBe('3h ago')
    expect(timeAgo('2026-10-20T10:00:00')).toBe('yesterday')
    expect(timeAgo('2026-10-17T12:00:00')).toBe('4 days ago')
    expect(timeAgo('2026-10-01T12:00:00')).toBe('1 Oct 2026')
  })
})

describe('colour families (the colour filter and sort)', () => {
  it('puts a paint in the family you would', () => {
    expect(familyOf('#000000')).toBe('Black')
    expect(familyOf('#ffffff')).toBe('White')
    expect(familyOf('#808080')).toBe('Grey')
    expect(familyOf('#d81e1e')).toBe('Red')
    expect(familyOf('#f28c1e')).toBe('Orange')
    expect(familyOf('#f2d21e')).toBe('Yellow')
    expect(familyOf('#3c8c3c')).toBe('Green')
    expect(familyOf('#1e4fd8')).toBe('Blue')
    expect(familyOf('#7a2fd8')).toBe('Purple')
    expect(familyOf('#e64ca0')).toBe('Pink')
    expect(familyOf('#5a3a1e')).toBe('Brown')
    expect(familyOf(null)).toBe(null)
  })
  it('sorts by family first, so all the reds come before the greens', () => {
    const order = ['#3c8c3c', '#d81e1e', '#000000', '#1e4fd8'].sort((a, b) => colourKey(a) - colourKey(b))
    expect(order.map(familyOf)).toEqual(['Red', 'Green', 'Blue', 'Black'])
    expect(colourKey(null)).toBeGreaterThan(colourKey('#000000'))     // (no colour: last)
  })
})
