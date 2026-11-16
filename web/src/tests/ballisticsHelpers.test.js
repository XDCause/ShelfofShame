import { describe, expect, it } from 'vitest'
import { airLabel, clicksFor, compareWithDope, gapText } from '../modules/shooting/ballisticsHelpers.js'

const predicted = [{ m: 100, elevation: 0 }, { m: 200, elevation: 1.5 }, { m: 300, elevation: 4 }]

describe('compareWithDope', () => {
  it('sets your confirmed and entered rows beside the prediction, ignoring estimates', () => {
    const dope = [{ m: 200, elevation: 1.8, source: 'confirmed' }, { m: 300, elevation: 3, source: 'estimate' }, { m: 100, elevation: 0, source: 'entered' }]
    const rows = compareWithDope(predicted, dope)
    expect(rows.map((r) => r.mine)).toEqual([0, 1.8, null])
    expect(rows[1].gap).toBe(0.3)
    expect(rows[2].gap).toBeNull()
  })
  it('copes with nothing at all', () => {
    expect(compareWithDope(null, null)).toEqual([])
    expect(compareWithDope(predicted, undefined)[0].mine).toBeNull()
  })
})

describe('the small formatters', () => {
  it('turns an elevation into clicks only when the click size is known', () => {
    expect(clicksFor(1.5, 0.25)).toBe(6)
    expect(clicksFor(1.5, null)).toBeNull()
    expect(clicksFor(null, 0.25)).toBeNull()
  })
  it('says how far apart you are', () => {
    expect(gapText(0.3, 'MOA')).toBe('+0.30 MOA (yours needs more)')
    expect(gapText(-1, 'MIL')).toBe('-1.00 MIL (yours needs less)')
    expect(gapText(0.02, 'MOA')).toBe('agrees')
    expect(gapText(null, 'MOA')).toBe('')
  })
  it('labels a session by its air', () => {
    expect(airLabel({ temp_c: 21, pressure_hpa: 1012, humidity_pct: 55 })).toBe('21°C, 1012 hPa, 55%')
    expect(airLabel({ temp_c: null })).toBe('')
  })
})
