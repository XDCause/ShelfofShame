// Language learning > Read's pure helpers (tested in tests/languageRead.test.js). The API marks each sentence's words
// (language_sentences.py: pieces [{text, word, unknown}]); these keep the page's list in step without asking again.

// "More": the new set after the ones already shown, without showing one twice.
export function mergeMore(shown, more) {
  const have = new Set(shown.map((s) => s.sentence_id))
  return [...shown, ...more.filter((s) => !have.has(s.sentence_id))]
}

// A word just added to the deck is known: no longer highlighted in any sentence on the page.
export function learnWord(sentences, word) {
  return sentences.map((s) => (s.unknown.includes(word) ? {
    ...s,
    unknown: s.unknown.filter((w) => w !== word),
    pieces: s.pieces.map((p) => (p.word === word ? { ...p, unknown: false } : p)),
  } : s))
}

// The words of a sentence as written ("está" for esta), for the word box's heading.
export const writtenAs = (sentence, word) => sentence.pieces.find((p) => p.word === word)?.text ?? word

// How a sentence sits against what you know: "every word known", "1 new word", "3 new words".
export const newWords = (s) => (s.unknown.length === 0 ? 'every word known' : `${s.unknown.length} new word${s.unknown.length === 1 ? '' : 's'}`)
