import { describe, expect, it } from 'vitest'
import { learnWord, mergeMore, newWords, writtenAs } from '../modules/language/readParts.js'

const s = (id, unknown, pieces = []) => ({ sentence_id: id, unknown, pieces })
const dog = s(1, ['come', 'esta'], [
  { text: 'El', word: 'el', unknown: false }, { text: ' ', word: null, unknown: false },
  { text: 'come', word: 'come', unknown: true }, { text: ' ', word: null, unknown: false },
  { text: 'Está', word: 'esta', unknown: true },
])

describe('Read: the list on the page', () => {
  it('adds "More" after what is shown, never twice', () => {
    expect(mergeMore([s(1, []), s(2, [])], [s(2, []), s(3, [])]).map((x) => x.sentence_id)).toEqual([1, 2, 3])
    expect(mergeMore([], [s(5, [])]).map((x) => x.sentence_id)).toEqual([5])
  })
  it('stops highlighting a word once it is in the deck', () => {
    const [after, other] = learnWord([dog, s(2, ['gato'])], 'come')
    expect(after.unknown).toEqual(['esta'])
    expect(after.pieces.filter((p) => p.unknown).map((p) => p.text)).toEqual(['Está'])
    expect(other.unknown).toEqual(['gato'])
    expect(dog.unknown).toEqual(['come', 'esta'])            // (the old list is left alone)
  })
  it('shows a word as written, and how many are new', () => {
    expect(writtenAs(dog, 'esta')).toBe('Está')
    expect(writtenAs(dog, 'nada')).toBe('nada')
    expect(newWords(s(1, []))).toBe('every word known')
    expect(newWords(s(1, ['a']))).toBe('1 new word')
    expect(newWords(dog)).toBe('2 new words')
  })
})
