// The offline copy's pieces that run in the page: noticing an answer came from the copy, and finding what to save.
import { describe, expect, it, vi } from 'vitest'
import { isOffline, noteAnswer, onOfflineChange } from '../offline/state.js'
import { idsIn } from '../offline/saveAll.js'

vi.mock('../modules/index.js', () => ({ MODULES: [] }))      // (saveAll walks every hobby's pages: none needed here)

const answer = (headers = {}) => new Response('{}', { headers })

describe('the Offline banner', () => {
  it('shows while answers come from the copy and goes when the server answers', () => {
    const seen = []
    const stop = onOfflineChange((now) => seen.push(now))
    noteAnswer(answer())
    expect(isOffline()).toBe(false)
    noteAnswer(answer({ 'X-OTC-Saved': '2026-11-11T09:00:00Z' }))          // a saved answer
    expect(isOffline()).toBe(true)
    noteAnswer(answer({ 'X-OTC-Offline': '1' }))                          // "can't reach it" (a change, or nothing saved)
    noteAnswer(answer())                                                 // the server's back
    expect(isOffline()).toBe(false)
    expect(seen).toEqual([true, false])                                  // told only when it changes
    stop()
  })
})

describe('Save everything now', () => {
  it('finds every id in an answer, however it is shaped', () => {
    expect(idsIn([{ trip_id: 1 }, { trip_id: 2 }], 'trip_id')).toEqual([1, 2])
    expect(idsIn({ books: [{ book_id: 7 }], counts: { read: 1 } }, 'book_id')).toEqual([7])
    // goals come with their children: each one once
    expect(idsIn({ goals: [{ goal_id: 1, children: [{ goal_id: 2 }] }, { goal_id: 2 }] }, 'goal_id')).toEqual([1, 2])
    expect(idsIn(null, 'hike_id')).toEqual([])
  })
})
