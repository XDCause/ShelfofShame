import { describe, expect, it } from 'vitest'
import { pickDetail, STATUS_LABEL } from '../modules/videogames/backlogHelpers.js'

describe('pickDetail', () => {
  it('says the time from SteamHunters and the achievements left', () => {
    const g = { estimate_minutes: 150, sh_median_minutes: 150, achievements_total: 20, left_to_get: 12 }
    expect(pickDetail(g, 600)).toBe('about 2.5 h to 100% (SteamHunters) · 12 of 20 achievements left')
  })
  it('falls back to your own median, in minutes when short', () => {
    expect(pickDetail({ estimate_minutes: 45, sh_median_minutes: null, achievements_total: 0 }, 45)).toBe('about 45 min (your median finished game)')
  })
  it('is empty when nothing is known', () => {
    expect(pickDetail({ estimate_minutes: null, achievements_total: 0 }, null)).toBe('')
  })
  it('names every status', () => {
    expect(STATUS_LABEL.backlog).toBe('Backlog')
  })
})
