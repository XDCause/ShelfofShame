import { describe, expect, it } from 'vitest'
import { forecastText, goalPaceText } from '../modules/reading/paceText.js'

describe('forecastText', () => {
  it('says nothing without a forecast', () => {
    expect(forecastText(null)).toBe('')
  })
  it('gives the pace and the finish day', () => {
    expect(forecastText({ pages_per_day: 12, finish_on: '2026-11-20' })).toMatch(/^12 pages a day lately · finish around .*20/)
    expect(forecastText({ pages_per_day: 7.5 })).toBe('7.5 pages a day lately')
  })
})

describe('goalPaceText', () => {
  it('is blank with no goal or once reached', () => {
    expect(goalPaceText({ goal: null })).toBe('')
    expect(goalPaceText({ goal: 12, reached: true, projected: 20, behind_by: 0 })).toBe('')
  })
  it('says behind or on track', () => {
    expect(goalPaceText({ goal: 12, projected: 8.6, behind_by: 4 })).toBe('4 books behind at your pace (on track for 9)')
    expect(goalPaceText({ goal: 12, projected: 1.2, behind_by: 1 })).toBe('1 book behind at your pace (on track for 1)')
    expect(goalPaceText({ goal: 12, projected: 13.4, behind_by: 0 })).toBe('On track for 13 books this year')
  })
})
