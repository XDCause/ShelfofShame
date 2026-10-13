import { useState } from 'react'
import { MOOD_WORDS, MOODS, moodOf } from './moods.js'

// The face beside a page's title: how the day felt. Tap it to pick one of five moods and a word
// or two; tap the chosen mood again to clear it. Saves as you tap (onChange({mood, mood_words})).
export default function MoodPicker({ mood, words = [], onChange }) {
  const [open, setOpen] = useState(false)
  const [own, setOwn] = useState('')
  const current = moodOf(mood)
  const choices = [...new Set([...MOOD_WORDS, ...words])]

  const pickMood = (id) => onChange({ mood: id === mood ? null : id })
  const toggleWord = (w) => onChange({ mood_words: words.includes(w) ? words.filter((x) => x !== w) : [...words, w] })
  const addOwn = () => {
    const w = own.trim().toLowerCase()
    if (w && !words.includes(w)) onChange({ mood_words: [...words, w] })
    setOwn('')
  }

  return (
    <div className="mood">
      <button type="button" className={current ? `mood-face ${current.tone}` : 'mood-face empty'}
        onClick={() => setOpen(!open)} aria-expanded={open}
        aria-label={current ? `Mood: ${current.label}. Change it` : 'How did it feel? Set a mood'}
        title={current ? `${current.label}${words.length ? ` · ${words.join(', ')}` : ''}` : 'How did it feel?'}>
        {current?.face ?? '🙂'}
      </button>
      {open && (
        <div className="mood-panel" role="group" aria-label="Mood">
          <p className="mood-question">How did it feel?</p>
          <div className="mood-choices">
            {MOODS.map((m) => (
              <button key={m.id} type="button" className={`mood-choice ${m.tone}`} aria-pressed={mood === m.id}
                onClick={() => pickMood(m.id)}>
                <span className="mood-choice-face" aria-hidden="true">{m.face}</span>{m.label}
              </button>
            ))}
          </div>
          <div className="chips mood-words" aria-label="A word or two">
            {choices.map((w) => (
              <button key={w} type="button" className="chip-filter" aria-pressed={words.includes(w)}
                onClick={() => toggleWord(w)} disabled={!words.includes(w) && words.length >= 5}>{w}</button>
            ))}
            <input value={own} onChange={(e) => setOwn(e.target.value)} maxLength={24} placeholder="+ your own"
              aria-label="Add your own word" disabled={words.length >= 5}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addOwn() } }} onBlur={addOwn} />
          </div>
          <button type="button" className="plain small" onClick={() => setOpen(false)}>Done</button>
        </div>
      )}
    </div>
  )
}
