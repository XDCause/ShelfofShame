import { describe, expect, it } from 'vitest'
import { parText } from '../modules/sudoku/techniqueHelpers.js'

describe('parText', () => {
  it('says how a solve time compares with the usual for its level', () => {
    expect(parText(0.8)).toBe('20% under')
    expect(parText(1.5)).toBe('50% over')
    expect(parText(1)).toBe('on par')
    expect(parText(null)).toBe('–')
  })
})
