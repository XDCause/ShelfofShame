import { describe, expect, it } from 'vitest'
import { check, core, makeLesson, noteParts, orderRight, rng, scoreOf, splitGap, tokens } from '../modules/language/lessonMaker.js'

const LESSON = {
  id: 'es-u01-l1',
  items: [
    { es: 'hola', en: 'hello', kind: 'word', accept_en: ['hi'] },
    { es: 'buenos días', en: 'good morning', kind: 'phrase', accept: ['buen día'] },
    { es: 'el café', en: 'the coffee', kind: 'word' },
    { es: 'gracias', en: 'thank you', kind: 'word', accept_en: ['thanks'] },
    { es: 'adiós', en: 'goodbye', kind: 'word', accept_en: ['bye'] },
    { es: 'chao', en: 'bye', kind: 'word' },
    { es: 'sí', en: 'yes', kind: 'word' },
    { es: 'no', en: 'no', kind: 'word' },
  ],
  sentences: [
    { es: 'Hola, me llamo Ana.', en: 'Hello, my name is Ana.', gap: 'llamo' },
    { es: '¿Cómo estás?', en: 'How are you?', gap: 'estás', accept_en: ['How are you doing?'] },
    { es: 'Sí, gracias.', en: 'Yes, thank you.', gap: 'gracias' },
    { es: 'Buenos días, Carlos.', en: 'Good morning, Carlos.', gap: 'Buenos' },
    { es: 'No, gracias.', en: "No, thanks.", gap: 'No' },
    { es: 'Adiós, Ana.', en: 'Goodbye, Ana.', gap: 'Adiós' },
    { es: 'El café, por favor.', en: "The coffee, please.", gap: 'café' },
  ],
}

describe('makeLesson', () => {
  const ex = makeLesson(LESSON, { seed: 7, earlier: [{ es: 'el perro', en: 'the dog' }] })
  it('makes the exercises in the README order', () => {
    const kinds = ex.map((e) => e.kind)
    const order = ['introduce', 'match', 'pick', 'type', 'listen', 'order', 'gap', 'translate']
    expect([...new Set(kinds)]).toEqual(order)
    expect(kinds.filter((k) => k === 'introduce')).toHaveLength(8)
    expect(kinds.filter((k) => k === 'match')).toHaveLength(2)
    expect(kinds.filter((k) => k === 'pick')).toHaveLength(3)
    expect(kinds.filter((k) => k === 'gap')).toHaveLength(3)
    expect(new Set(ex.map((e) => e.key)).size).toBe(ex.length)
  })
  it('is the same for the same seed, different for another', () => {
    expect(makeLesson(LESSON, { seed: 7 })).toEqual(makeLesson(LESSON, { seed: 7 }))
    expect(JSON.stringify(makeLesson(LESSON, { seed: 8 }))).not.toEqual(JSON.stringify(makeLesson(LESSON, { seed: 7 })))
    expect(rng('a')()).toBe(rng('a')())
  })
  it('pairs every match, and pick has its answer among unambiguous options', () => {
    for (const m of ex.filter((e) => e.kind === 'match')) {
      expect(m.left).toHaveLength(m.pairs.length)
      expect(new Set(m.right)).toEqual(new Set(m.pairs.map((p) => p.en)))
    }
    for (let seed = 1; seed < 30; seed++) {
      for (const p of makeLesson(LESSON, { seed }).filter((e) => e.kind === 'pick')) {
        expect(p.options).toContain(p.item.en)
        expect(new Set(p.options).size).toBe(p.options.length)
        if (p.item.es === 'adiós') expect(p.options).not.toContain('bye')         // (its other meaning: not a wrong option)
      }
    }
  })
  it('gives order tiles that make the sentence, and gap options with the gap', () => {
    for (let seed = 1; seed < 30; seed++) {
      for (const e of makeLesson(LESSON, { seed })) {
        if (e.kind === 'order') {
          const texts = e.tiles.map((t) => t.text)
          for (const w of e.answer) expect(texts).toContain(w)
          expect(texts.join(' ')).not.toBe(e.answer.join(' '))
          expect(orderRight(e.answer, tokens(e.sentence.es))).toBe(true)
        }
        if (e.kind === 'gap') {
          expect(e.options).toContain(e.sentence.gap)
          expect(e.before + e.sentence.gap + e.after).toBe(e.sentence.es)
        }
      }
    }
    const hola = makeLesson(LESSON, { seed: 3 }).find((e) => e.kind === 'order' && e.sentence.es.startsWith('Hola'))
    if (hola) expect(hola.answer[0]).toBe('hola')                                 // (lower case: it doesn't give the start away)
  })
})

describe('check', () => {
  it('takes the answer, its alternatives, accents and typos (said so)', () => {
    expect(check('Buenos dias', ['buenos días']).verdict).toBe('accents')
    expect(check('buen día', ['buenos días', 'buen día']).verdict).toBe('right')
    expect(check('graciass', ['gracias']).verdict).toBe('typo')
    expect(check('cafe', ['el café'], { articles: true }).verdict).toBe('article')
    expect(check('perro', ['el café'], { articles: true }).ok).toBe(false)
    expect(check('', ['hola']).verdict).toBe('empty')
  })
  it('reads English contractions either way, punctuation and case aside', () => {
    expect(check("hello my name's ana", ['Hello, my name is Ana.']).verdict).toBe('right')
    expect(check("I'm well", ['I am well.']).verdict).toBe('right')
    expect(check('I do not know', ["I don't know."]).verdict).toBe('right')
    expect(check('Hello', ['Hello, my name is Ana.']).ok).toBe(false)             // (a part isn't the whole)
  })
})

describe('the rest', () => {
  it('splits a gap, tiles and cores', () => {
    expect(splitGap('Es el es.', 'es')).toEqual({ before: 'Es el ', after: '.' })
    expect(tokens('¿Cómo estás, Ana?')).toEqual(['Cómo', 'estás', 'Ana'])
    expect(core('el café')).toBe('café')
    expect(scoreOf({ a: true, b: false, c: true, d: true })).toBe(75)
    expect(scoreOf({})).toBe(100)
  })
  it('reads notes as text: bold runs and lines, never HTML', () => {
    expect(noteParts('A **bold** word.\n<b>x</b>')).toEqual([
      [{ text: 'A ', bold: false }, { text: 'bold', bold: true }, { text: ' word.', bold: false }],
      [{ text: '<b>x</b>', bold: false }]])
  })
})
