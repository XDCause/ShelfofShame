import { describe, expect, it } from 'vitest'
import { epdOf, formatLine, gamesText, mineText, pickReply, progressText, suggestColour, uciSquares } from '../modules/chess/openingHelpers.js'

describe('formatLine', () => {
  it('numbers White\'s moves', () => {
    expect(formatLine(['e4', 'e5', 'Nf3', 'Nc6'])).toBe('1.e4 e5 2.Nf3 Nc6')
    expect(formatLine([])).toBe('')
  })
  it('says 1... when a line starts with Black', () => {
    expect(formatLine(['e5', 'Nf3'], 1)).toBe('1...e5 2.Nf3')
  })
})

describe('epdOf', () => {
  it('drops the move counters', () => {
    expect(epdOf('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1')).toBe('rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3')
  })
})

describe('pickReply', () => {
  const options = [{ san: 'c5', share: 60 }, { san: 'e5', share: 30 }, { san: 'e6', share: 10 }]
  it('picks by how often a reply is played', () => {
    expect(pickReply(options, 0).san).toBe('c5')
    expect(pickReply(options, 0.59).san).toBe('c5')
    expect(pickReply(options, 0.61).san).toBe('e5')
    expect(pickReply(options, 0.95).san).toBe('e6')
    expect(pickReply(options, 0.999999).san).toBe('e6')
  })
  it('has nothing to pick when the line ends', () => {
    expect(pickReply(undefined)).toBeNull()
    expect(pickReply([])).toBeNull()
  })
  it('takes the first when the shares are missing', () => {
    expect(pickReply([{ san: 'a' }, { san: 'b' }], 0.9).san).toBe('a')
  })
})

describe('small text helpers', () => {
  it('uciSquares', () => expect(uciSquares('e7e8q')).toEqual({ from: 'e7', to: 'e8' }))
  it('gamesText', () => {
    expect([812, 1500, 34000, 1250000].map(gamesText)).toEqual(['812', '1.5k', '34k', '1.3M'])
  })
  it('mineText', () => {
    expect(mineText({ games: 0 })).toBeNull()
    expect(mineText({ games: 7, wins: 3, draws: 1, losses: 3 })).toBe("You've reached this position 7 times: +3 =1 -3")
    expect(mineText({ games: 1, wins: 1, draws: 0, losses: 0 })).toContain('1 time:')
  })
  it('progressText', () => {
    expect(progressText({ total: 0 })).toBe('No cards yet')
    expect(progressText({ total: 20, learned: 12, due: 3, new: 5 })).toBe('12 learned, 3 due, 5 new of 20')
    expect(progressText({ total: 4, learned: 4, due: 0, new: 0 })).toBe('4 learned of 4')
  })
  it('suggestColour', () => {
    expect(suggestColour('Sicilian Defense: Najdorf Variation')).toBe('black')
    expect(suggestColour("King's Indian Attack")).toBe('black')
    expect(suggestColour('Italian Game')).toBe('white')
    expect(suggestColour('London System')).toBe('white')
  })
})
