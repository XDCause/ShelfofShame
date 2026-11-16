import { describe, expect, it } from 'vitest'
import { stepRows, yearRows } from '../components/modelStatsRows.js'
import { rackBrands, rackGroups } from '../core/supplies/rack.js'

describe('yearRows', () => {
  it('has a row for every year between the first and the last, zero when none were finished', () => {
    const rows = yearRows([{ year: 2024, kits: 2, minis: 12, minutes: 300 }, { year: 2026, kits: 1, minis: 1, minutes: 0 }])
    expect(rows.map((r) => [r.label, r.value])).toEqual([['2024', 2], ['2025', 0], ['2026', 1]])
    expect(rows[0].tip).toContain('2 kits')
  })
  it('is empty with nothing finished', () => {
    expect(yearRows([])).toEqual([])
    expect(yearRows(undefined)).toEqual([])
  })
})

describe('stepRows', () => {
  it('lists the steps biggest first with a readable time, leaving out empty ones', () => {
    const rows = stepRows([{ step: 'Built', minutes: 30 }, { step: 'Painted', minutes: 135 }, { step: 'Decals', minutes: 0 }])
    expect(rows.map((r) => [r.label, r.text])).toEqual([['Painted', '2 h 15 min'], ['Built', '30 min']])
  })
})

describe('rackGroups', () => {
  const paint = (name, code, brand, extra = {}) => ({ supply_id: Math.random(), name, product_code: code, brand, category: 'Paint', stock_status: 'OK', ...extra })
  const all = [
    paint('Flat White', 'T81702', 'Tamiya', { swatch: '#ffffff' }),
    paint('Flat Black', 'T81701', 'Tamiya', { swatch: '#111111', stock_status: 'Low' }),
    paint('Mephiston Red', '21-04', 'Citadel', { swatch: '#dd2222' }),
    { ...paint('Cement', 'T87012', 'Tamiya'), category: 'Glue / Cement' },
  ]
  it('is paints only, grouped by brand A-Z, each brand in code order', () => {
    const groups = rackGroups(all)
    expect(groups.map((g) => g.brand)).toEqual(['Citadel', 'Tamiya'])
    expect(groups[1].items.map((s) => s.product_code)).toEqual(['T81701', 'T81702'])
    expect(rackBrands(all)).toEqual(['Citadel', 'Tamiya'])
  })
  it('filters by brand, colour family, text and low / out', () => {
    expect(rackGroups(all, { brand: 'Citadel' })).toHaveLength(1)
    expect(rackGroups(all, { family: 'Red' })[0].items[0].name).toBe('Mephiston Red')
    expect(rackGroups(all, { text: '81702' })[0].items.map((s) => s.name)).toEqual(['Flat White'])
    expect(rackGroups(all, { attention: true })[0].items.map((s) => s.name)).toEqual(['Flat Black'])
  })
})
