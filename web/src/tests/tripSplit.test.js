import { describe, expect, it } from 'vitest'
import { heard } from '../core/journal/JournalTools.jsx'
import { nextShare } from '../modules/travel/TripSplit.jsx'

describe('nextShare (who shares a cost; empty = everyone)', () => {
  const everyone = [1, 2, 3]
  it('taking one person off from "everyone" leaves the rest', () => {
    expect(nextShare([], everyone, 2)).toEqual([1, 3])
  })
  it('putting the last one back goes to "everyone" (empty)', () => {
    expect(nextShare([1, 3], everyone, 2)).toEqual([])
  })
  it('never ends up with nobody: taking the last person off means everyone', () => {
    expect(nextShare([2], everyone, 2)).toEqual([])
  })
  it('adds a person in the trip\'s order', () => {
    expect(nextShare([3], everyone, 1)).toEqual([1, 3])
  })
})

describe('heard (dictated text)', () => {
  it('trims and ends with a space, ready for the next words', () => {
    expect(heard('  went for a walk ')).toBe('went for a walk ')
  })
})
