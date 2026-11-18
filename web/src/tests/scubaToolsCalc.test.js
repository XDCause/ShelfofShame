import { describe, expect, it } from 'vitest'
import { ata, bestMix, clockOf, ead, mod, ppO2, sac } from '../modules/scuba/diveCalc.js'

describe('diveCalc', () => {
  it('works out the MOD', () => {
    expect(mod(32, 1.4)).toBe(33.8)          // 33.75 m
    expect(mod(32, 1.6)).toBe(40)
    expect(mod(21, 1.4)).toBe(56.7)
    expect(mod(100, 1.6)).toBe(6)
  })
  it('works out the equivalent air depth', () => {
    expect(ead(32, 30)).toBe(24.4)
    expect(ead(21, 30)).toBe(30)
  })
  it('finds the richest mix for a depth', () => {
    expect(bestMix(30, 1.4)).toBe(35)         // 1.4 / 4 = 35%
    expect(bestMix(33, 1.4)).toBe(32)
    expect(bestMix(3, 1.4)).toBe(100)
    expect(bestMix(60, 1.4)).toBe(20)
  })
  it('gives ppO2 at depth', () => {
    expect(ppO2(32, 30)).toBe(1.28)
    expect(ppO2(21, 0)).toBe(0.21)
    expect(ata(20)).toBe(3)
  })
  it('works out SAC from a dive', () => {
    // 140 bar of a 12 L tank in 45 min at 14 m average: 1680 L / 45 / 2.4
    expect(sac({ startBar: 200, endBar: 60, tankL: 12, minutes: 45, avgDepth: 14 })).toBe(15.6)
    expect(sac({ startBar: '200', endBar: '', tankL: 12, minutes: 45, avgDepth: 14 })).toBeNull()
    expect(sac({ startBar: 100, endBar: 150, tankL: 12, minutes: 45, avgDepth: 14 })).toBeNull()
    expect(sac({ startBar: 200, endBar: 60, tankL: 12, minutes: 0, avgDepth: 14 })).toBeNull()
  })
  it('formats a time', () => {
    expect(clockOf(754)).toBe('12:34')
    expect(clockOf(5)).toBe('0:05')
  })
})
