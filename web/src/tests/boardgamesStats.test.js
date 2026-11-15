import { describe, expect, it } from 'vitest'
import { firstPlayerText, streakText, unplayedGames } from '../modules/boardgames/statsHelpers.js'

const g = (name, plays, last_played, extra = {}) => ({ game_id: name, name, plays, last_played, kind: 'game', status: 'Owned', ...extra })

describe('unplayedGames', () => {
  it('finds owned base games never played, and ones idle for a year', () => {
    const games = [g('Never', 0, null), g('Old', 3, '2025-11-01'), g('Fresh', 2, '2026-06-01'), g('Edge', 1, '2025-11-16'),
      g('Wanted', 0, null, { status: 'Wanted' }), g('Add-on', 0, null, { kind: 'expansion' })]
    const r = unplayedGames(games, '2026-11-16')
    expect(r.never.map((x) => x.name)).toEqual(['Never'])
    expect(r.stale.map((x) => x.name)).toEqual(['Old'])      // a year ago to the day is not yet "not in 12 months"
  })
})

describe('text helpers', () => {
  it('says how going first did', () => {
    expect(firstPlayerText({ plays: 12, wins: 7, rate: 58, chance: 25 })).toBe('Won 7 of 12 (58%) - chance alone would give about 25%')
    expect(firstPlayerText({ plays: 0 })).toBeNull()
  })
  it('says a streak', () => {
    expect(streakText(3)).toBe('3 in a row')
    expect(streakText(0)).toBe('none')
  })
})
