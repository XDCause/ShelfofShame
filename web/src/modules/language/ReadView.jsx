import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { BookIcon, LanguageIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { speak } from './answers.js'
import { LanguagePicker } from './LanguageViews.jsx'
import { useLanguages } from './langParts.js'
import { learnWord, mergeMore, newWords, writtenAs } from './readParts.js'

// Read: real sentences from Tatoeba (tatoeba.org, CC BY 2.0 FR; loaded once on the PC by load-tatoeba.ps1) at your level -
// "just right" has one word you don't know yet (i+1), "easy" none (the API's language_sentences.py says how it knows).
// The sentence in the language, tap to show the English (that marks it read), hear it in the browser's own voice. A word
// you don't know is highlighted: tap it to see it in other sentences or put the sentence in your deck as a cloze card.

const LEVELS = [['right', 'Just right'], ['easy', 'Easy'], ['any', 'Any']]
const TATOEBA = 'https://tatoeba.org'

export function ReadView() {
  const { languages, current, pick } = useLanguages()
  const { openPanel } = useApp()
  if (!languages) return <p className="muted loading">Loading...</p>
  if (!current) {
    return (
      <section className="page lng-page">
        <EmptyState Icon={LanguageIcon} title="Which language?" action="+ Add a language" onAction={() => openPanel('langlanguage', {})}>
          Add the language you're learning, then read real sentences at your level here.
        </EmptyState>
      </section>
    )
  }
  return (
    <section className="page lng-page">
      <LanguagePicker languages={languages} current={current} pick={pick} />
      <Reader key={current.language_id} language={current} />
    </section>
  )
}

function Reader({ language }) {
  const { showToast, changed } = useApp()
  const [level, setLevel] = useState('right')
  const [word, setWord] = useState(null)
  const [find, setFind] = useState('')
  const [data, setData] = useState(null)
  const [list, setList] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lid = language.language_id

  const fetchSet = useCallback(() => api.languageSentences({ language_id: lid, level, word, limit: 10 }), [lid, level, word])
  useEffect(() => {
    let live = true
    setData(null)
    setError('')
    fetchSet().then((d) => { if (live) { setData(d); setList(d.sentences) } }).catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [fetchSet])

  const more = async () => {
    setBusy(true)
    try {
      const d = await fetchSet()
      setData(d)
      setList((l) => mergeMore(l, d.sentences))
    } catch (e) {
      showToast(e.message)
    }
    setBusy(false)
  }
  const lookUp = (w) => {
    setWord(w)
    setFind('')
    window.scrollTo?.({ top: 0, behavior: 'smooth' })
  }
  const add = async (s, w) => {
    try {
      const r = await api.addLanguageSentenceCard(s.sentence_id, { language_id: lid, word: w })
      setList((l) => learnWord(l, r.word))
      showToast(`"${writtenAs(s, r.word)}" is in your deck, in this sentence`)
      changed()
    } catch (e) {
      showToast(e.message)
    }
  }
  const pickLevel = (l) => { setWord(null); setLevel(l) }
  const submit = (e) => {
    e.preventDefault()
    if (find.trim()) lookUp(find.trim())
  }

  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  if (!data.course) {
    return (
      <EmptyState Icon={BookIcon} title={`No sentences for ${language.name} yet`}>
        The sentences to read come from Tatoeba, and they're there for Spanish so far.
      </EmptyState>
    )
  }
  if (!data.total) {
    return (
      <EmptyState Icon={BookIcon} title="No sentences loaded">
        Real example sentences come from Tatoeba, downloaded once on the PC: run <code>.\load-tatoeba.ps1</code> in the app's folder,
        then come back here.
      </EmptyState>
    )
  }
  const voice = language.voice || data.course
  return (
    <div className="lngr-page">
      <div className="lngr-bar">
        <div className="chip-row" role="group" aria-label="Which sentences">
          {LEVELS.map(([l, label]) => (
            <button key={l} type="button" className="chip-filter" aria-pressed={!word && level === l} onClick={() => pickLevel(l)}>
              {label}{l !== 'any' && ` (${(data.counts[l] ?? 0).toLocaleString()})`}</button>
          ))}
        </div>
        <form className="lngr-find" onSubmit={submit} role="search">
          <label className="lngr-find-label">
            <span className="visually-hidden">Find sentences with a word</span>
            <input type="search" value={find} onChange={(e) => setFind(e.target.value)} placeholder="Find a word" lang={voice}
              autoCapitalize="off" spellCheck="false" maxLength={60} />
          </label>
          <button type="submit" className="secondary small">Find</button>
        </form>
      </div>
      {word ? (
        <p className="lngr-head">Sentences with <strong lang={voice}>{word}</strong>
          <button type="button" className="plain small" onClick={() => setWord(null)}>Back to your level</button></p>
      ) : (
        <p className="muted small lngr-head">{data.known_words ? `${data.known_words.toLocaleString()} words you know (from your cards and lessons)` : 'No words in your deck yet: add cards or finish lessons, and sentences at your level show up here.'}
          {' '}· {data.total.toLocaleString()} sentences</p>
      )}
      {list.length === 0 ? (
        <p className="muted lngr-none">{word ? `No sentences with "${word}".`
          : level === 'any' ? 'Nothing to read.'
            : `None ${level === 'right' ? 'just right' : 'easy'} yet: add words to your deck (or finish lessons), or read Any - tap a highlighted word to learn it.`}</p>
      ) : (
        <ul className="lngr-list">
          {list.map((s) => <Sentence key={s.sentence_id} s={s} voice={voice} languageId={lid} onLookUp={lookUp} onAdd={add} />)}
        </ul>
      )}
      {list.length > 0 && <button type="button" className="secondary lngr-more" disabled={busy} onClick={more}>{busy ? 'Finding more...' : 'More'}</button>}
      <p className="muted small lngr-credit">Sentences from <a href={TATOEBA} target="_blank" rel="noopener noreferrer">Tatoeba (tatoeba.org)</a>,{' '}
        <a href={data.licence_url} target="_blank" rel="noopener noreferrer">CC BY 2.0 FR</a> - each links to its page there.</p>
    </div>
  )
}

function Sentence({ s, voice, languageId, onLookUp, onAdd }) {
  const { showToast } = useApp()
  const [shown, setShown] = useState(false)
  const [open, setOpen] = useState(null)
  const reveal = () => {
    if (!shown && !s.seen) api.seenLanguageSentence(s.sentence_id, languageId).catch(() => {})
    setShown(!shown)
  }
  const openWord = open && s.unknown.includes(open) ? open : null
  return (
    <li className="card lngr-sentence">
      <p className="lngr-text" lang={voice}>
        {s.pieces.map((p, i) => (p.unknown ? (
          <button key={i} type="button" className="inline lngr-word" aria-expanded={openWord === p.word}
            onClick={() => setOpen(openWord === p.word ? null : p.word)}>{p.text}</button>
        ) : <span key={i}>{p.text}</span>))}
      </p>
      {openWord && (
        <div className="lngr-wordbox" role="group" aria-label={`The word ${writtenAs(s, openWord)}`}>
          <strong lang={voice}>{writtenAs(s, openWord)}</strong>
          <button type="button" className="secondary small" onClick={() => onAdd(s, openWord)}>Add to deck</button>
          <button type="button" className="plain small" onClick={() => onLookUp(openWord)}>In other sentences</button>
        </div>
      )}
      {shown && <ul className="lngr-english">{s.english.map((e) => <li key={e}>{e}</li>)}</ul>}
      <div className="lngr-actions">
        <button type="button" className="secondary small" aria-expanded={shown} onClick={reveal}>{shown ? 'Hide the English' : 'Show the English'}</button>
        <button type="button" className="plain small" onClick={() => speak(s.text, voice) || showToast('This browser has no voice for it')}>▶ Say it</button>
        <span className="muted small lngr-new">{newWords(s)}</span>
      </div>
      <p className="small lngr-source"><a href={s.url} target="_blank" rel="noopener noreferrer">Tatoeba #{s.sentence_id}</a></p>
    </li>
  )
}
