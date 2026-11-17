import { describe, expect, it, vi } from 'vitest'
import { alternatives, checkAnswer, clozeParts, distance, minutesText, normalise, plainFront, speak, voiceFor } from '../modules/language/answers.js'

describe('checkAnswer', () => {
  it('takes the right answer whatever the case, punctuation or notes in brackets', () => {
    expect(checkAnswer('El perro', 'el perro (m.)').verdict).toBe('right')
    expect(checkAnswer('  ¿Qué tal?  ', 'qué tal').verdict).toBe('right')
    expect(checkAnswer('el perro', 'el perro').suggest).toBe(3)
  })
  it('forgives accents (and ß / ss) but says so, suggesting Hard', () => {
    expect(checkAnswer('cafe', 'café')).toEqual({ verdict: 'accents', suggest: 2, match: 'café' })
    expect(checkAnswer('strasse', 'Straße').verdict).toBe('accents')
    expect(checkAnswer('nino', 'niño').verdict).toBe('accents')
  })
  it('calls one slip in a word a typo (two in a long one), not in a short one', () => {
    expect(checkAnswer('mañama', 'mañana').verdict).toBe('typo')
    expect(checkAnswer('biblioteac', 'biblioteca').verdict).toBe('typo')
    expect(checkAnswer('sol', 'sal').verdict).toBe('wrong')
    expect(checkAnswer('gato', 'perro')).toEqual({ verdict: 'wrong', suggest: 1, match: 'perro' })
  })
  it('accepts any of several answers', () => {
    expect(alternatives('to go, to leave / to depart')).toEqual(['to go', 'to leave', 'to depart'])
    expect(checkAnswer('to leave', 'to go, to leave')).toEqual({ verdict: 'right', suggest: 3, match: 'to leave' })
  })
  it('an empty answer is just shown (Again suggested)', () => {
    expect(checkAnswer('   ', 'hola')).toMatchObject({ verdict: 'empty', suggest: 1 })
  })
})

describe('the helpers', () => {
  it('normalises and measures', () => {
    expect(normalise('Ça va?', true)).toBe('ca va')
    expect(distance('kitten', 'sitting')).toBe(3)
  })
  it('reads cloze sentences, with hints', () => {
    const c = clozeParts('Ayer {{fui::ir}} al {{cine}}.')
    expect(c.answer).toBe('fui cine')
    expect(c.full).toBe('Ayer fui al cine.')
    expect(c.blanked).toBe('Ayer ____ al ____.')
    expect(c.parts[1]).toEqual({ answer: 'fui', hint: 'ir' })
    expect(plainFront({ kind: 'cloze', front: 'Ayer {{fui}} al cine' })).toBe('Ayer fui al cine')
  })
  it('finds a voice from the language name', () => {
    expect(voiceFor(' spanish ')).toBe('es-ES')
    expect(voiceFor('Klingon')).toBeNull()
  })
  it('writes minutes as hours', () => {
    expect(minutesText(45)).toBe('45 min')
    expect(minutesText(80)).toBe('1h 20m')
    expect(minutesText(120)).toBe('2h')
  })
  it('speaks with the browser, and says when it cannot', () => {
    const spoken = []
    vi.stubGlobal('SpeechSynthesisUtterance', function Utterance(text) { this.text = text })
    vi.stubGlobal('speechSynthesis', { cancel: () => {}, speak: (u) => spoken.push(u), getVoices: () => [{ lang: 'es-MX' }] })
    expect(speak('hola', 'es-ES')).toBe(true)
    expect(spoken[0]).toMatchObject({ text: 'hola', lang: 'es-ES', voice: { lang: 'es-MX' } })
    vi.stubGlobal('speechSynthesis', undefined)
    expect(speak('hola', 'es-ES')).toBe(false)
    vi.unstubAllGlobals()
  })
})
