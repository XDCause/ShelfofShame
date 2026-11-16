import { describe, expect, it } from 'vitest'
import { cellColour, cellKey, dropNoteMarks, noteColour, noteKey, toggleMark } from '../modules/sudoku/sudokuMarks.js'

describe('colour marks', () => {
  it('colours a cell, changes the colour, and takes it off by pressing the same one', () => {
    let m = toggleMark({}, cellKey(12), 2)
    expect(cellColour(m, 12)).toBe(2)
    m = toggleMark(m, cellKey(12), 3)
    expect(cellColour(m, 12)).toBe(3)
    m = toggleMark(m, cellKey(12), 3)
    expect(m).toEqual({})
  })
  it('keeps a note\'s colour apart from its cell\'s', () => {
    const m = toggleMark(toggleMark({}, cellKey(5), 1), noteKey(5, 7), 4)
    expect(cellColour(m, 5)).toBe(1)
    expect(noteColour(m, 5, 7)).toBe(4)
    expect(noteColour(m, 5, 8)).toBe(0)
  })
  it('forgets a cell\'s note colours when a digit goes in, but keeps the cell\'s own', () => {
    const m = dropNoteMarks({ 5: 1, '5:7': 4, '50:7': 2 }, 5)
    expect(m).toEqual({ 5: 1, '50:7': 2 })
  })
})
