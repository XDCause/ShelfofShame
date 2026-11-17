// Language learning's pure helpers (tested in tests/language.test.js): checking a typed answer, cloze sentences, the
// voice for a language, and saying something with the browser's own speech (no outside service).

// "El perro (m.)" -> "el perro": lower case, no punctuation or (notes), spaces tidied; loose = accents and ß / æ / œ too.
export function normalise(text, loose = false) {
  let s = String(text ?? '').toLowerCase().replace(/\([^)]*\)/g, ' ')
  if (loose) s = s.normalize('NFD').replace(/\p{M}/gu, '').replace(/ß/g, 'ss').replace(/æ/g, 'ae').replace(/œ/g, 'oe')
  return s.normalize('NFC').replace(/[^\p{L}\p{N}\s'-]/gu, ' ').replace(/\s+/g, ' ').trim()
}

// Edit distance (insert, delete, change one letter).
export function distance(a, b) {
  if (a === b) return 0
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i++) {
    const row = [i]
    for (let j = 1; j <= b.length; j++) row[j] = Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
    prev = row
  }
  return prev[b.length]
}

// The answers a card's text allows: "to go, to leave / to depart" -> three.
export const alternatives = (expected) => String(expected ?? '').split(/[,;/]|\bor\b/).map((s) => s.trim()).filter(Boolean)

// What you typed against what was wanted:
//   right    the same (case, punctuation and notes in brackets don't count)
//   accents  right but for accents (or ß / ss) - counts, but says so
//   typo     one letter off (two in a long word)
//   wrong    / empty
// suggest: the grade it points to (3 Good, 2 Hard, 1 Again); match: the alternative it was closest to.
export function checkAnswer(typed, expected) {
  const said = normalise(typed)
  const options = alternatives(expected)
  const whole = String(expected ?? '').trim()
  if (!said) return { verdict: 'empty', suggest: 1, match: options[0] ?? whole }
  if (!options.includes(whole)) options.unshift(whole)
  let best = { verdict: 'wrong', suggest: 1, match: options[0], off: Infinity }
  for (const option of options) {
    const want = normalise(option)
    if (!want) continue
    if (said === want) return { verdict: 'right', suggest: 3, match: option }
    if (normalise(typed, true) === normalise(option, true)) {
      best = { verdict: 'accents', suggest: 2, match: option, off: 0 }
      continue
    }
    const off = distance(normalise(typed, true), normalise(option, true))
    const allowed = want.length >= 8 ? 2 : want.length >= 4 ? 1 : 0
    if (off <= allowed && best.verdict !== 'accents' && off < best.off) best = { verdict: 'typo', suggest: 2, match: option, off }
  }
  return { verdict: best.verdict, suggest: best.suggest, match: best.match }
}

// "Ayer {{fui::ir}} al cine" -> parts [{text: 'Ayer '}, {answer: 'fui', hint: 'ir'}, {text: ' al cine'}], answer 'fui',
// full 'Ayer fui al cine'.
export function clozeParts(front) {
  const parts = []
  const re = /\{\{(.+?)\}\}/g
  let at = 0
  let m
  while ((m = re.exec(front ?? '')) !== null) {
    if (m.index > at) parts.push({ text: front.slice(at, m.index) })
    const [answer, hint] = m[1].split('::')
    parts.push({ answer: answer.trim(), hint: hint?.trim() || null })
    at = m.index + m[0].length
  }
  if (at < (front ?? '').length) parts.push({ text: front.slice(at) })
  const blanks = parts.filter((p) => p.answer != null)
  return {
    parts,
    answer: blanks.map((p) => p.answer).join(' '),
    full: parts.map((p) => p.text ?? p.answer).join(''),
    blanked: parts.map((p) => p.text ?? '____').join(''),
  }
}

// The text a card shows on its front (a cloze's sentence without the braces).
export const plainFront = (card) => (card.kind === 'cloze' ? clozeParts(card.front).full : card.front)

// A language's voice for the browser's speech, from its name (you can set any BCP-47 tag on the language).
export const VOICES = {
  Spanish: 'es-ES', French: 'fr-FR', German: 'de-DE', Italian: 'it-IT', Portuguese: 'pt-BR', Japanese: 'ja-JP', Korean: 'ko-KR',
  Mandarin: 'zh-CN', Chinese: 'zh-CN', Cantonese: 'zh-HK', Dutch: 'nl-NL', Russian: 'ru-RU', Arabic: 'ar-SA', Hindi: 'hi-IN',
  Indonesian: 'id-ID', Vietnamese: 'vi-VN', Thai: 'th-TH', Greek: 'el-GR', Swedish: 'sv-SE', Norwegian: 'nb-NO', Danish: 'da-DK',
  Polish: 'pl-PL', Turkish: 'tr-TR', Hebrew: 'he-IL', Irish: 'ga-IE', Welsh: 'cy-GB', Finnish: 'fi-FI', Ukrainian: 'uk-UA',
  Tagalog: 'fil-PH', Czech: 'cs-CZ', Hungarian: 'hu-HU', Romanian: 'ro-RO', Malay: 'ms-MY', Auslan: null, English: 'en-AU',
}
export const voiceFor = (name) => VOICES[Object.keys(VOICES).find((k) => k.toLowerCase() === String(name ?? '').trim().toLowerCase())] ?? null

// Say it in the language's voice. False when the browser can't speak (or has no voice for it): the button says so.
export function speak(text, lang, rate = 0.9) {
  try {
    const synth = typeof window !== 'undefined' && window.speechSynthesis
    if (!synth || !text) return false
    synth.cancel()
    const u = new window.SpeechSynthesisUtterance(text)
    if (lang) {
      u.lang = lang
      const base = lang.split('-')[0].toLowerCase()
      const voices = synth.getVoices?.() ?? []
      u.voice = voices.find((v) => v.lang === lang) ?? voices.find((v) => v.lang?.toLowerCase().startsWith(base)) ?? null
    }
    u.rate = rate
    synth.speak(u)
    return true
  } catch {
    return false
  }
}

// "1h 20m", "45 min"
export const minutesText = (m) => {
  const n = Math.round(m ?? 0)
  return n >= 60 ? `${Math.floor(n / 60)}h${n % 60 ? ` ${n % 60}m` : ''}` : `${n} min`
}
export const plural = (n, one, many = `${one}s`) => `${(n ?? 0).toLocaleString()} ${n === 1 ? one : many}`
