import { describe, expect, it } from 'vitest'
import { dayLabel, firstPair, photosByDate, spanText } from '../modules/gardening/photoTimeline.js'

const logs = [
  { happened_on: '2026-03-10', text: 'Flowering', photos: [{ photo_id: 5, url: '/p/5' }] },
  { happened_on: '2026-01-02', text: null, photos: [{ photo_id: 2, url: '/p/2' }, { photo_id: 1, url: '/p/1' }] },
  { happened_on: '2026-02-01', photos: [] },
]

describe('photosByDate', () => {
  it('flattens every note photo, oldest first', () => {
    const p = photosByDate(logs)
    expect(p.map((x) => x.photo_id)).toEqual([1, 2, 5])
    expect(p[2]).toEqual({ photo_id: 5, url: '/p/5', on: '2026-03-10', text: 'Flowering' })
  })
  it('copes with nothing', () => {
    expect(photosByDate(undefined)).toEqual([])
    expect(photosByDate([{ happened_on: '2026-01-01' }])).toEqual([])
  })
})

describe('labels', () => {
  it('counts days from the start', () => {
    expect(dayLabel('2026-01-12', '2026-01-02')).toBe('Day 10')
    expect(dayLabel('2026-01-02', '2026-01-02')).toBe('Day 0')
    expect(dayLabel('2025-12-30', '2026-01-02')).toBe('Before it started')
    expect(dayLabel('2026-01-02', null)).toBe('')
  })
  it('says how far apart two photos are', () => {
    expect(spanText('2026-01-02', '2026-01-02')).toBe('same day')
    expect(spanText('2026-01-02', '2026-01-03')).toBe('1 day')
    expect(spanText('2026-01-02', '2026-01-09')).toBe('7 days')
    expect(spanText('2026-01-02', '2026-01-23')).toBe('3 weeks')
    expect(spanText('2026-04-02', '2026-01-02')).toBe('3 months')
  })
  it('starts with the oldest and newest', () => {
    expect(firstPair(photosByDate(logs))).toEqual([1, 5])
    expect(firstPair([])).toEqual([null, null])
  })
})
