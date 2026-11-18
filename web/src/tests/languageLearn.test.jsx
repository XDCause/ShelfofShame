// Language learning's Learn page (modules/language/LanguageLearn.jsx) drawn with the API faked: the course path, a
// language without a course offered one, and a lesson played start to finish - right answers, one wrong one that comes
// back at the end, the keys (Enter checks, then continues), "Can't listen now", the finish screen and what it sends.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { LearnView } from '../modules/language/LanguageLearn.jsx'
import { tokens } from '../modules/language/lessonMaker.js'

vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  const names = ['languages', 'languageCourse', 'languageLesson', 'finishLanguageLesson', 'updateLanguage']
  return { ...real, api: { ...real.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } }
})

const LANG = { language_id: 1, name: 'Spanish', voice: 'es-MX', course: 'es', active: true }
const LESSON = {
  id: 'es-u01-l1', course: 'es', title: 'Greetings', unit: 1, unit_title: 'Hola', number: 1, of: 3, cefr: 'A1', goal: 'Greet people.',
  notes: 'Say **hola** to anyone.\n<b>not html</b>',
  items: [
    { es: 'hola', en: 'hello', kind: 'word' }, { es: 'buenos días', en: 'good morning', kind: 'phrase' },
    { es: 'gracias', en: 'thank you', kind: 'word' }, { es: 'adiós', en: 'goodbye', kind: 'word' },
    { es: 'sí', en: 'yes', kind: 'word' }, { es: 'el café', en: 'the coffee', kind: 'word', note: 'A man-word.' },
    { es: 'bien', en: 'well', kind: 'word' }, { es: 'mal', en: 'bad', kind: 'word' },
  ],
  sentences: [
    { es: 'Hola, Ana.', en: 'Hello, Ana.', gap: 'Hola' }, { es: 'Muy bien, gracias.', en: 'Very well, thank you.', gap: 'gracias' },
    { es: 'Adiós, Carlos.', en: 'Goodbye, Carlos.', gap: 'Adiós' }, { es: 'Sí, el café.', en: 'Yes, the coffee.', gap: 'café' },
    { es: 'Buenos días, Ana.', en: 'Good morning, Ana.', gap: 'días' }, { es: 'Mal, gracias.', en: 'Bad, thanks.', gap: 'Mal' },
    { es: 'Bien, Ana.', en: 'Well, Ana.', gap: 'Bien' },
  ],
  earlier: [], next: { id: 'es-u01-l2', title: 'Goodbyes', unit: 1, unit_title: 'Hola' },
}
const PATH = {
  language: LANG, course: { code: 'es', name: 'Spanish', units: 1, lessons: 2, levels: ['A1'] }, done: 1, total: 2,
  next: { id: 'es-u01-l2', title: 'Goodbyes', unit: 1, unit_title: 'Hola' }, available: [],
  units: [{ unit: 1, title: 'Hola', cefr: 'A1', goal: 'Greet people.', done: 1, total: 2, lessons: [
    { id: 'es-u01-l1', title: 'Greetings', items: 8, done: true, best: 90, last_score: 90, times: 1, unlocked: true, next: false },
    { id: 'es-u01-l2', title: 'Goodbyes', items: 8, done: false, best: null, times: 0, unlocked: true, next: true },
  ] }],
}

const app = { refreshKey: 0, changed: vi.fn(), showToast: vi.fn(), openPanel: vi.fn(), navigate: vi.fn() }
const draw = (url) => render(
  <AppContext.Provider value={app}><MemoryRouter initialEntries={[url]}><LearnView /></MemoryRouter></AppContext.Provider>)

beforeEach(() => {
  vi.clearAllMocks()
  api.languages.mockResolvedValue([LANG])
  api.languageCourse.mockResolvedValue(PATH)
  api.languageLesson.mockResolvedValue(LESSON)
  api.finishLanguageLesson.mockResolvedValue({ run_id: 1, added: 15, words: 8, sentences: 7, unit_done: false, next: LESSON.next, first_time: true })
})
afterEach(cleanup)

describe('the course path', () => {
  it('shows the units, the lessons and Continue', async () => {
    draw('/language/learn')
    expect(await screen.findByText('Spanish course')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Continue: Goodbyes/ }).getAttribute('href')).toBe('/language/learn?lesson=es-u01-l2&language=1')
    expect(screen.getByRole('link', { name: /Lesson 1: Greetings - done, best 90%/ })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Lesson 2: Goodbyes - next/ })).toBeTruthy()
  })
  it('offers a course to a language without one', async () => {
    api.languageCourse.mockResolvedValue({ language: { ...LANG, course: null }, course: null, missing: null, suggested: 'es',
      available: [{ code: 'es', name: 'Spanish', units: 30, lessons: 120, levels: ['A1', 'A2'] }] })
    api.updateLanguage.mockResolvedValue({})
    draw('/language/learn')
    fireEvent.click(await screen.findByRole('button', { name: 'Follow it for Spanish' }))
    await waitFor(() => expect(api.updateLanguage).toHaveBeenCalledWith(1, { course: 'es' }))
  })
})

// Answer whatever exercise is showing: right, unless told to get it wrong.
function play(card, wrong = false) {
  const kind = card.dataset.kind
  const q = within(card)
  const big = () => card.querySelector('.lngc-big').textContent
  if (kind === 'introduce') { fireEvent.click(q.getByRole('button', { name: 'Continue' })); return kind }
  if (kind === 'listen') { fireEvent.click(q.getByRole('button', { name: "Can't listen now" })); return kind }
  if (kind === 'match') {
    const [left, right] = card.querySelectorAll('.lngc-col')
    for (const b of [...left.querySelectorAll('button')]) {
      fireEvent.click(b)
      fireEvent.click(within(right).getByRole('button', { name: LESSON.items.find((i) => i.es === b.textContent).en }))
    }
  } else if (kind === 'pick') {
    const item = LESSON.items.find((i) => i.es === big())
    fireEvent.click(within(q.getByRole('group', { name: 'Options' })).getByRole('button', { name: item.en }))
    fireEvent.click(q.getByRole('button', { name: 'Check' }))
  } else if (kind === 'type') {
    const item = LESSON.items.find((i) => i.en === big())
    const box = q.getByLabelText(/^In /)
    fireEvent.change(box, { target: { value: wrong ? 'nada' : item.es } })
    fireEvent.submit(box.closest('form'))
  } else if (kind === 'order') {
    const s = LESSON.sentences.find((x) => x.en === card.querySelector('.lngc-prompt').textContent)
    const bank = q.getByRole('group', { name: 'Words' })
    for (const w of tokens(s.es)) {
      fireEvent.click([...bank.querySelectorAll('button:not([disabled])')].find((b) => b.textContent.toLowerCase() === w.toLowerCase()))
    }
    fireEvent.keyDown(card, { key: 'Enter' })                    // (Enter checks)
  } else if (kind === 'gap') {
    const s = LESSON.sentences.find((x) => x.en === card.querySelector('.lngc-meaning').textContent)
    fireEvent.click(within(q.getByRole('group', { name: 'Options' })).getByRole('button', { name: s.gap }))
    fireEvent.click(q.getByRole('button', { name: 'Check' }))
  } else if (kind === 'translate') {
    const s = LESSON.sentences.find((x) => x.es === card.querySelector('.lngc-sentence').textContent)
    const box = q.getByLabelText('In English')
    fireEvent.change(box, { target: { value: s.en } })
    fireEvent.submit(box.closest('form'))
  }
  return kind
}

describe('a lesson', () => {
  it('plays from the notes to the finish, a mistake coming back at the end', async () => {
    const { container } = draw('/language/learn?lesson=es-u01-l1&language=1')
    expect(await screen.findByRole('heading', { name: 'Greetings' })).toBeTruthy()
    expect(container.querySelector('.lngc-notes strong').textContent).toBe('hola')
    expect(container.querySelector('.lngc-notes b')).toBeNull()             // (text, never HTML)
    fireEvent.click(screen.getByRole('button', { name: 'Start the lesson' }))
    const seen = []
    let wrongOnce = true
    for (let i = 0; i < 80; i++) {
      const card = container.querySelector('.lngc-ex')
      if (!card) break
      const kind = card.dataset.kind
      const wrong = kind === 'type' && wrongOnce
      if (wrong) wrongOnce = false
      seen.push(card.dataset.key.includes('again') ? `${kind} again` : kind)
      play(card, wrong)
      const feedback = container.querySelector('.lngc-feedback')
      if (feedback) {
        expect(feedback.className).toContain(wrong ? 'wrong' : 'right')
        if (wrong) expect(feedback.textContent).toContain('Not quite')
        fireEvent.keyDown(screen.getByRole('button', { name: 'Continue' }), { key: 'Enter' })   // (Enter continues)
      }
    }
    expect(seen).toContain('type again')
    expect(seen.at(-1)).toBe('type again')                                  // the mistake, last
    expect(seen).not.toContain('listen again')
    await waitFor(() => expect(api.finishLanguageLesson).toHaveBeenCalled())
    const [langId, lessonId, body] = api.finishLanguageLesson.mock.calls[0]
    expect([langId, lessonId]).toEqual([1, 'es-u01-l1'])
    expect(body.mistakes).toBe(1)
    const scored = seen.filter((k) => !['introduce', 'listen'].includes(k) && !k.endsWith('again')).length
    expect(body.score).toBe(Math.round((100 * (scored - 1)) / scored))
    expect(await screen.findByText(/Lesson done/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Next lesson: Goodbyes' }).getAttribute('href')).toBe('/language/learn?lesson=es-u01-l2&language=1')
    expect(screen.getByText(/8 words and 7 sentences went into your Spanish cards/)).toBeTruthy()
  })
})
