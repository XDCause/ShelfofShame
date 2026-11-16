import { describe, expect, it } from 'vitest'
import { clock, minutesText, secondsLeft } from '../core/focus/focusMath.js'

describe('clock', () => {
  it('shows minutes and seconds, and hours when there are some', () => {
    expect(clock(1500)).toBe('25:00')
    expect(clock(59)).toBe('00:59')
    expect(clock(3725)).toBe('1:02:05')
  })
  it('never goes below zero', () => {
    expect(clock(-5)).toBe('00:00')
  })
})

describe('secondsLeft', () => {
  const running = { status: 'running', remaining_seconds: 100 }
  it('counts down from when the server answered', () => {
    expect(secondsLeft(running, 1000, 1000)).toBe(100)
    expect(secondsLeft(running, 1000, 31500)).toBe(70)
    expect(secondsLeft(running, 1000, 500000)).toBe(0)
  })
  it('stands still while paused, and is 0 with no session', () => {
    expect(secondsLeft({ status: 'paused', remaining_seconds: 80 }, 1000, 99999)).toBe(80)
    expect(secondsLeft(null, 0, 0)).toBe(0)
  })
})

describe('minutesText', () => {
  it('says minutes, or hours and minutes', () => {
    expect(minutesText(45)).toBe('45 min')
    expect(minutesText(60)).toBe('1 h')
    expect(minutesText(95)).toBe('1 h 35 min')
    expect(minutesText(0)).toBe('0 min')
  })
})
