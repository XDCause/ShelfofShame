import { describe, expect, it } from 'vitest'
import { clock, minutesText, placeText, places, seatTotal, seatsOut } from '../modules/boardgames/tableParts.jsx'

describe('board games at the table', () => {
  it('adds a score up the way the API does: typed, else the score sheet, else the +/- taps', () => {
    expect(seatTotal({ score: '12', parts: { A: 1 }, adds: [5] })).toBe(12)
    expect(seatTotal({ parts: { Birds: '30', Eggs: '4.5', Food: '' } })).toBe(34.5)
    expect(seatTotal({ adds: [1, 5, -2] })).toBe(4)
    expect(seatTotal({ adds: [] })).toBe(null)
  })

  it('places players by score, sharing a tie, for highest and lowest scoring only', () => {
    const seats = [{ score: 8 }, { score: 10 }, { score: 8 }, {}]
    expect(places(seats, 'highest')).toEqual([2, 1, 2, null])
    expect(places(seats, 'lowest')).toEqual([1, 3, 1, null])
    expect(places(seats, 'coop')).toEqual([null, null, null, null])
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22].map(placeText)).toEqual(['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd'])
  })

  it('shows the clock and minutes', () => {
    expect(clock(0)).toBe('0:00')
    expect(clock(725)).toBe('12:05')
    expect(clock(3925)).toBe('1:05:25')
    expect(minutesText(45)).toBe('45 min')
    expect(minutesText(65)).toBe('1 h 05')
  })

  it('sends known players by id and new ones by name, with numbers as numbers', () => {
    expect(seatsOut([{ player_id: 3, name: 'Sam', score: '7', adds: [] }, { name: 'Kim', parts: { A: '2', B: '' }, won: true }])).toEqual([
      { player_id: 3, score: 7, parts: null, adds: [], team: null, colour: null, won: null },
      { name: 'Kim', score: null, parts: { A: 2 }, adds: [], team: null, colour: null, won: true },
    ])
  })
})
