import { describe, expect, it } from 'vitest'
import { checkedText, conditionFacts, dateOf, dueText, heatLevel, hoursText, inClosedSeason, monthDay, num, oneADay, plural, ruleFacts, stars, timeOf, toIso, tripMinutes, tripName } from '../modules/fishing/fishFormat.js'

describe('fishing formats', () => {
  it('reads numbers and counts', () => {
    expect(num(52.5)).toBe('52.5')
    expect(num(30)).toBe('30')
    expect(num(null)).toBe('—')
    expect(plural(1, 'trip')).toBe('1 trip')
    expect(plural(3, 'fish', 'fish')).toBe('3 fish')
    expect(hoursText(2.25)).toBe('2.3 h')
    expect(stars(4)).toBe('★★★★☆')
  })

  it('writes a rule the way you typed it, and nothing when none is typed', () => {
    expect(ruleFacts({ min_cm: 40, max_cm: 70, bag: 5, closed_from: '06-01', closed_to: '08-31', no_take: false }))
      .toEqual(['min 40 cm', 'max 70 cm', 'bag 5', 'closed 1 Jun - 31 Aug'])
    expect(ruleFacts({ no_take: true, bag: 0 })).toEqual(['no take'])
    expect(ruleFacts({ min_cm: null, max_cm: null, bag: null, closed_from: null, closed_to: null, no_take: false })).toEqual([])
    expect(monthDay('11-05')).toBe('5 Nov')
    expect(checkedText(null, String)).toBe('never checked')
    expect(checkedText('2026-11-03', (d) => d)).toBe('checked on 2026-11-03')
  })

  it('knows a closed season, also one that wraps over New Year', () => {
    expect(inClosedSeason('2026-07-04', '06-01', '08-31')).toBe(true)
    expect(inClosedSeason('2026-09-01', '06-01', '08-31')).toBe(false)
    expect(inClosedSeason('2026-12-25', '11-01', '02-15')).toBe(true)
    expect(inClosedSeason('2026-01-20', '11-01', '02-15')).toBe(true)
    expect(inClosedSeason('2026-05-20', '11-01', '02-15')).toBe(false)
    expect(inClosedSeason('2026-05-20', null, null)).toBe(false)
  })

  it('goes between an ISO time and the local date and time boxes', () => {
    const iso = toIso('2026-11-14', '05:45')
    expect(dateOf(iso)).toBe('2026-11-14')
    expect(timeOf(iso)).toBe('05:45')
    expect(toIso('', '05:45')).toBeNull()
    expect(tripMinutes({ started_at: toIso('2026-11-14', '05:00'), ended_at: toIso('2026-11-14', '07:30') })).toBe(150)
    expect(tripMinutes({ started_at: toIso('2026-11-14', '05:00'), ended_at: null })).toBeNull()
  })

  it('names a trip and counts days to a due date', () => {
    expect(tripName({ spot_name: 'Wellington Point' })).toBe('Wellington Point')
    expect(tripName({ target: 'flathead' })).toBe('flathead')
    expect(tripName({})).toBe('Fishing trip')
    const now = new Date('2026-11-18T10:00:00')
    expect(dueText('2026-11-30', now)).toBe('due in 12 days')
    expect(dueText('2026-11-18', now)).toBe('due today')
    expect(dueText('2026-11-15', now)).toBe('overdue by 3 days')
  })

  it('shades a heat grid cell against the biggest, and keeps one point a day', () => {
    expect(heatLevel(0, 10)).toBe(0)
    expect(heatLevel(1, 10)).toBe(1)
    expect(heatLevel(10, 10)).toBe(4)
    expect(oneADay([{ x: '2026-11-01', y: 1 }, { x: '2026-11-01', y: 2 }, { x: '2026-11-02', y: 3 }])).toEqual([{ x: '2026-11-01', y: 2 }, { x: '2026-11-02', y: 3 }])
  })

  it('turns a saved conditions snapshot into facts and skips what is missing', () => {
    const facts = conditionFacts({ moon_phase: 'Full moon', moon_pct: 99.6, wind_kmh: 14.2, tide: [{ time: '2026-11-14T06:12', kind: 'high' }, { time: '2026-11-14T12:30', kind: 'low' }] })
    expect(facts.map((f) => f.label)).toEqual(['Moon', 'Tide', 'Wind'])
    expect(facts[1].value).toBe('H 06:12 · L 12:30')
    expect(conditionFacts(null)).toEqual([])
  })
})
