// A course lesson's exercises, made in the browser from its content (api/app/language_course.py serves the content;
// data/courses/README.md is the format). Pure and deterministic for a given seed (tests/lessonMaker.test.js), so a lesson
// plays differently each time but a test can pin it down. In the README's order:
//   introduce  each item: the Spanish, its meaning, spoken, its note
//   match      tap the pairs (up to two rounds of up to 5-6 pairs)
//   pick       an item: choose its meaning (wrong options from the lesson and earlier lessons)
//   type       an item's meaning: type it in the language
//   listen     hear an item, type it
//   order      a sentence's meaning: put its words in order (tappable tiles, one or two extra)
//   gap        a sentence with its gap word missing: choose it
//   translate  a sentence: type it in English (close answers count)
import { distance, normalise } from './answers.js'

const ARTICLES = new Set(['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas'])
const WORD = /[\p{L}]+(?:['’-][\p{L}]+)*/gu

// A seeded random number generator (mulberry32), from a number or a string.
export function rng(seed) {
  let a = typeof seed === 'number' ? seed >>> 0 : [...String(seed)].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0, 2166136261)
  return () => {
    a = (a + 0x6D2B79F5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function shuffle(list, rand) {
  const out = [...list]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

export const words = (text) => String(text ?? '').match(WORD) ?? []

// "el café" -> "café"; "¿cómo estás?" -> "cómo estás"
export function core(es) {
  const ws = words(es).map((w) => w.toLowerCase())
  return (ws.length > 1 && ARTICLES.has(ws[0]) ? ws.slice(1) : ws).join(' ')
}

// A sentence's tiles: its words as written, without the punctuation around them ("¿Cómo" -> "Cómo", "Ana." -> "Ana").
export const tokens = (es) => String(es ?? '').split(/\s+/).map((t) => t.replace(/^[¿¡"«(“]+|[.,!?;:"»)”…]+$/gu, '')).filter(Boolean)

// The sentence split around its gap word (its first whole-word use).
export function splitGap(es, gap) {
  const escaped = gap.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const m = new RegExp(`(?<![\\p{L}\\p{N}])${escaped}(?![\\p{L}\\p{N}])`, 'u').exec(es)
  return m ? { before: es.slice(0, m.index), after: es.slice(m.index + gap.length) } : { before: `${es} `, after: '' }
}

// English contractions read the same either way: "I'm" = "I am".
const CONTRACTIONS = [[/\b(i)'m\b/g, '$1 am'], [/\b(you|we|they)'re\b/g, '$1 are'], [/\blet's\b/g, 'let us'], [/\b(\w+)'s\b/g, '$1 is'],   // (a possessive too - both sides read alike)
  [/\bcan't\b/g, 'cannot'], [/\bwon't\b/g, 'will not'], [/\b(\w+)n't\b/g, '$1 not'], [/\b(i|you|we|they)'ve\b/g, '$1 have'],
  [/\b(i|you|he|she|we|they)'ll\b/g, '$1 will'], [/\b(i|you|he|she|we|they)'d\b/g, '$1 would'], [/\blet's\b/g, 'let us']]
function plain(text, loose = false) {
  let s = normalise(String(text ?? '').replace(/[’‘]/g, "'"), loose)
  for (const [re, to] of CONTRACTIONS) s = s.replace(re, to)
  return s.replace(/\bcan not\b/g, 'cannot').replace(/\s+/g, ' ').trim()
}
const slack = (n) => (n < 4 ? 0 : n < 8 ? 1 : n < 20 ? 2 : 3)

// What you typed against the answers that count:
//   right    the same (case, punctuation and English contractions don't count)
//   accents  right but for accents                                   - counts, but says so
//   typo     a letter or two off (more slack in a longer answer)     - counts, but says so
//   article  a noun without its article ("café" for "el café")       - counts, but says so
//   wrong / empty
export function check(typed, answers, { articles = false } = {}) {
  const options = answers.filter(Boolean)
  const said = plain(typed)
  if (!said) return { verdict: 'empty', ok: false, match: options[0] }
  let best = null
  for (const option of options) {
    const want = plain(option)
    if (said === want) return { verdict: 'right', ok: true, match: option }
    if (plain(typed, true) === plain(option, true)) best = best ?? { verdict: 'accents', ok: true, match: option }
  }
  if (best) return best
  for (const option of options) {
    const want = plain(option, true)
    if (distance(plain(typed, true), want) <= slack(want.length)) return { verdict: 'typo', ok: true, match: option }
  }
  if (articles) {
    for (const option of options) {
      const ws = plain(option, true).split(' ')
      if (ws.length > 1 && ARTICLES.has(ws[0]) && plain(typed, true) === ws.slice(1).join(' ')) return { verdict: 'article', ok: true, match: option }
    }
  }
  return { verdict: 'wrong', ok: false, match: options[0] }
}

export const spanishAnswers = (thing) => [thing.es, ...(thing.accept ?? [])]
export const englishAnswers = (thing) => [thing.en, ...(thing.accept_en ?? [])]

// Does choosing `option` for `item` count as right? (its meaning, or one of its other meanings)
const means = (item, text) => englishAnswers(item).some((a) => plain(a) === plain(text))

function pickOptions(item, pool, rand, n = 4) {
  const wrong = []
  const seen = new Set([plain(item.en)])
  for (const other of shuffle(pool, rand)) {
    const p = plain(other.en)
    if (seen.has(p) || means(item, other.en) || means(other, item.en)) continue
    seen.add(p)
    wrong.push(other.en)
    if (wrong.length === n - 1) break
  }
  return shuffle([item.en, ...wrong], rand)
}

const capitalise = (w) => w.charAt(0).toUpperCase() + w.slice(1)
const isCapital = (w) => w.charAt(0) !== w.charAt(0).toLowerCase()

function gapOptions(sentence, lesson, rand) {
  const gap = sentence.gap
  const low = gap.toLowerCase()
  const candidates = new Set()
  for (const s of lesson.sentences) for (const w of words(s.es)) if (w.toLowerCase() !== low && !isCapital(w)) candidates.add(w)
  for (const i of lesson.items) { const c = core(i.es); if (c && !c.includes(' ') && c !== low) candidates.add(c) }
  for (const w of words(sentence.es)) candidates.delete(w.toLowerCase())     // (no word that's in the sentence already)
  const wrong = shuffle([...candidates], rand).slice(0, 3)
  return shuffle([gap, ...wrong.map((w) => (isCapital(gap) ? capitalise(w) : w))], rand)
}

function orderTiles(sentence, lesson, rand) {
  const answer = tokens(sentence.es)
  // the first word in lower case when the lesson writes it so elsewhere (so it doesn't give the start away; names keep theirs)
  const lowerSeen = new Set([...lesson.items.flatMap((i) => words(i.es)), ...lesson.sentences.flatMap((s) => tokens(s.es).slice(1))]
    .filter((w) => !isCapital(w)).map((w) => w.toLowerCase()))
  const shown = answer.map((w, i) => (i === 0 && lowerSeen.has(w.toLowerCase()) ? w.toLowerCase() : w))
  const inIt = new Set(answer.map((w) => w.toLowerCase()))
  const extras = shuffle([...new Set(lesson.items.map((i) => core(i.es)).filter((c) => c && !c.includes(' ') && !inIt.has(c)))], rand)
    .slice(0, answer.length > 6 ? 1 : 2)
  let tiles = shuffle([...shown, ...extras].map((text, id) => ({ id, text })), rand)
  if (tiles.length > 1 && tiles.map((t) => t.text).join(' ') === shown.join(' ')) tiles = [...tiles.slice(1), tiles[0]]
  return { answer: shown, tiles }
}

// Is a row of tiles the sentence? (case doesn't count: a tile's case is the shown one)
export const orderRight = (picked, answer) => picked.map((w) => w.toLowerCase()).join(' ') === answer.map((w) => w.toLowerCase()).join(' ')

function pairsFrom(items) {
  const es = new Set()
  const en = new Set()
  return items.filter((i) => {
    const a = plain(i.es)
    const b = plain(i.en)
    if (es.has(a) || en.has(b)) return false
    es.add(a)
    en.add(b)
    return true
  })
}

const take = (list, from, n) => (list.length ? Array.from({ length: Math.min(n, list.length) }, (_, k) => list[(from + k) % list.length]) : [])

// The lesson's exercises. earlier: items of earlier lessons (more wrong options to pick from).
export function makeLesson(lesson, { seed = 1, earlier = [] } = {}) {
  const rand = rng(seed)
  const items = lesson.items ?? []
  const sentences = lesson.sentences ?? []
  const out = []
  const add = (kind, extra) => out.push({ key: `${kind}-${out.length}`, kind, ...extra })
  for (const item of items) add('introduce', { item })

  const mixed = shuffle(items, rand)
  const pairs = pairsFrom(mixed).slice(0, 10)
  const rounds = pairs.length > 6 ? 2 : pairs.length >= 2 ? 1 : 0
  for (let r = 0; r < rounds; r++) {
    const these = pairs.slice(Math.round((r * pairs.length) / rounds), Math.round(((r + 1) * pairs.length) / rounds))
    add('match', { pairs: these.map((p) => ({ es: p.es, en: p.en })), left: shuffle(these.map((p) => p.es), rand), right: shuffle(these.map((p) => p.en), rand) })
  }
  const pool = [...items, ...earlier]
  for (const item of take(mixed, 0, 3)) add('pick', { item, options: pickOptions(item, pool, rand) })
  for (const item of take(mixed, 3, 3)) add('type', { item })
  for (const item of take(mixed, 6, 2)) add('listen', { item })

  const order = shuffle(sentences, rand)
  for (const sentence of take(order, 0, 2)) add('order', { sentence, ...orderTiles(sentence, lesson, rand) })
  for (const sentence of take(order, 2, 3)) add('gap', { sentence, ...splitGap(sentence.es, sentence.gap), options: gapOptions(sentence, lesson, rand) })
  for (const sentence of take(order, 5, 2)) add('translate', { sentence })
  return out
}

// Exercises that are scored (introducing isn't).
export const graded = (exercise) => exercise.kind !== 'introduce'

// The score: the share of scored exercises right the first time.
export const scoreOf = (firstTries) => {
  const marks = Object.values(firstTries)
  return marks.length ? Math.round((100 * marks.filter(Boolean).length) / marks.length) : 100
}

// The notes' text in parts: paragraphs (a line break each) of plain and **bold** runs - shown as React text, never as HTML.
export function noteParts(text) {
  return String(text ?? '').split('\n').map((line) => line.trim()).filter(Boolean)
    .map((line) => line.split(/\*\*(.+?)\*\*/g).map((run, i) => ({ text: run, bold: i % 2 === 1 })).filter((r) => r.text))
}
