import { describe, expect, it } from 'vitest'
import { orderModules } from '../modules/order.js'

const mods = ['Volleyball', 'Chess', 'Board games', 'Models', 'Reading'].map((name) => ({ id: name.toLowerCase().replace(' ', ''), name }))
const names = (list) => list.map((m) => m.name)

describe('orderModules', () => {
  it('is A-Z when nothing is starred', () => {
    expect(names(orderModules(mods, []))).toEqual(['Board games', 'Chess', 'Models', 'Reading', 'Volleyball'])
    expect(names(orderModules(mods))).toEqual(['Board games', 'Chess', 'Models', 'Reading', 'Volleyball'])
  })
  it('puts favourites first, each group A-Z (the order they were starred in does not matter)', () => {
    expect(names(orderModules(mods, ['volleyball', 'models']))).toEqual(['Models', 'Volleyball', 'Board games', 'Chess', 'Reading'])
  })
  it('ignores a favourite that is not a hobby, and leaves the original list alone', () => {
    const before = names(mods)
    expect(names(orderModules(mods, ['knitting']))).toEqual(['Board games', 'Chess', 'Models', 'Reading', 'Volleyball'])
    expect(names(mods)).toEqual(before)
  })
})
