import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { LanguageIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { checkAnswer, clozeParts, plural, speak } from './answers.js'
import { LanguagePicker } from './LanguageViews.jsx'
import { useLanguages } from './langParts.js'

// The review session (Anki's, with Clozemaster's and Duolingo's ways of asking): today's cards one at a time - learning
// cards first, then the ones due, then new ones (up to the language's new-a-day). Ask by:
//   Flip    see the word, think of the meaning, show it
//   Type    see the meaning, type the word (accents forgiven but pointed out; one slip in a long word is a typo)
//   Listen  hear it in the language's voice (the browser's own speech), type what you heard or just show it
// A cloze card always asks for its missing word. Grade it Again / Hard / Good / Easy (keys 1-4; Enter / Space shows
// the answer): each button says when you'd see it next (FSRS: api/app/srs.py). Again brings it back in this sitting.
// Undo takes the last answer back.

const MODES = [['flip', 'Flip'], ['type', 'Type'], ['listen', 'Listen']]
const GRADES = [[1, 'Again'], [2, 'Hard'], [3, 'Good'], [4, 'Easy']]
const VERDICT = { right: 'Right', accents: 'Right - mind the accents', typo: 'Nearly - a typo', wrong: 'Not quite', empty: 'Shown' }
const MODE_KEY = 'otc.language.mode'
const savedMode = () => { try { return window.localStorage.getItem(MODE_KEY) || 'flip' } catch { return 'flip' } }

export function ReviewView() {
  const { languages, current, pick } = useLanguages()
  if (!languages) return <p className="muted loading">Loading...</p>
  if (!current) return <NoLanguage />
  return (
    <section className="page lng-page">
      <LanguagePicker languages={languages} current={current} pick={pick} />
      <Session key={current.language_id} language={current} />
    </section>
  )
}

function NoLanguage() {
  const { openPanel } = useApp()
  return (
    <section className="page lng-page">
      <EmptyState Icon={LanguageIcon} title="Which language?" action="+ Add a language" onAction={() => openPanel('langlanguage', {})}>
        Add the language you're learning, then its words - and review them here a little every day.
      </EmptyState>
    </section>
  )
}

function Session({ language }) {
  const { openPanel, showToast, changed } = useApp()
  const [queue, setQueue] = useState(null)
  const [info, setInfo] = useState(null)
  const [mode, setModeState] = useState(savedMode)
  const [shown, setShown] = useState(false)
  const [typed, setTyped] = useState('')
  const [check, setCheck] = useState(null)
  const [busy, setBusy] = useState(false)
  const [tally, setTally] = useState({ answered: 0, remembered: 0 })
  const [last, setLast] = useState(null)
  const started = useRef(Date.now())
  const input = useRef(null)
  const voice = language.voice

  const load = useCallback(() => api.languageReview(language.language_id)
    .then((q) => { setQueue(q.cards); setInfo(q) }).catch((e) => showToast(e.message)), [language.language_id, showToast])
  useEffect(() => { load() }, [load])

  const card = queue?.[0] ?? null
  const cloze = card?.kind === 'cloze' ? clozeParts(card.front) : null
  const asking = cloze ? (mode === 'flip' ? 'flip' : 'type') : mode
  const expected = cloze ? cloze.answer : card?.front
  const sayText = cloze ? cloze.full : card?.front

  // each new card: a clean slate, the clock restarted, the voice (Listen), the cursor in the box
  useEffect(() => {
    if (!card) return
    setShown(false)
    setTyped('')
    setCheck(null)
    started.current = Date.now()
    if (mode === 'listen') speak(cloze ? cloze.full : card.front, voice)
    setTimeout(() => input.current?.focus(), 0)
  }, [card?.card_id, card?.reps, mode]) // eslint-disable-line react-hooks/exhaustive-deps -- (once per card shown, not per keystroke)

  const setMode = (m) => {
    setModeState(m)
    try { window.localStorage.setItem(MODE_KEY, m) } catch { /* (just for now) */ }
  }
  const reveal = () => {
    if (asking !== 'flip') setCheck(checkAnswer(typed, expected))
    setShown(true)
  }
  const grade = async (g) => {
    if (!card || busy) return
    setBusy(true)
    try {
      const seconds = Math.min(3600, Math.round((Date.now() - started.current) / 1000))
      const r = await api.answerLanguageCard(card.card_id, { grade: g, mode: cloze ? 'cloze' : mode, seconds })
      setLast({ reviewId: r.review_id, card })
      setTally((t) => ({ answered: t.answered + 1, remembered: t.remembered + (g > 1 ? 1 : 0) }))
      setQueue((q) => {
        const rest = q.slice(1)
        if (!r.again_today) return rest
        const at = Math.min(3, rest.length)                      // (back in a few cards)
        return [...rest.slice(0, at), r.card, ...rest.slice(at)]
      })
      if (queue.length === 1 && !r.again_today) changed()
    } catch (e) {
      showToast(e.message)
    }
    setBusy(false)
  }
  const undo = async () => {
    if (!last) return
    try {
      const back = await api.undoLanguageAnswer(last.reviewId)
      setQueue((q) => [back, ...q.filter((c) => c.card_id !== back.card_id)])
      setTally((t) => ({ answered: Math.max(0, t.answered - 1), remembered: t.remembered }))
      setLast(null)
    } catch (e) {
      showToast(e.message)
    }
  }

  // keys: Enter / Space shows the answer; 1-4 grade it
  useEffect(() => {
    const onKey = (e) => {
      if (!card || e.ctrlKey || e.metaKey || e.altKey || document.querySelector('aside.drawer')) return
      if (!shown && e.key === 'Enter') { e.preventDefault(); reveal() }
      else if (!shown && e.key === ' ' && e.target.tagName !== 'INPUT') { e.preventDefault(); reveal() }
      else if (shown && ['1', '2', '3', '4'].includes(e.key)) { e.preventDefault(); grade(Number(e.key)) }
      else if (shown && (e.key === 'Enter' || e.key === ' ') && e.target.tagName !== 'BUTTON') { e.preventDefault(); grade(check?.suggest ?? 3) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!queue) return <p className="muted loading">Loading...</p>
  const modeBar = (
    <div className="lng-modes" role="group" aria-label="Ask by">
      {MODES.map(([m, label]) => (
        <button key={m} type="button" className="chip-filter" aria-pressed={mode === m} onClick={() => setMode(m)}>{label}</button>
      ))}
    </div>
  )
  if (!card) {
    return (
      <div className="lng-review">
        {tally.answered > 0 ? (
          <section className="card lng-done" role="status">
            <h2>Done for today</h2>
            <p>{plural(tally.answered, 'answer')} · {Math.round((100 * tally.remembered) / tally.answered)}% remembered</p>
            {info?.next_due && <p className="muted small">The next card comes due on {new Date(info.next_due).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'short' })}.</p>}
            <div className="button-row">
              {last && <button type="button" className="plain" onClick={undo}>Undo the last answer</button>}
              <button type="button" className="secondary" onClick={() => openPanel('langstudy', { languageId: language.language_id })}>Log other study</button>
              <Link className="button plain" to="/language/today">Today →</Link>
            </div>
          </section>
        ) : (
          <EmptyState Icon={LanguageIcon} title={language.cards ? 'Nothing to review' : 'No cards yet'}
            action={language.cards ? '+ Add a card' : '+ Add your first words'} onAction={() => openPanel('langcard', { languageId: language.language_id })}>
            {language.cards ? `You're up to date in ${language.name}${info?.new_left === 0 ? ` - and today's ${language.new_per_day} new cards are done` : ''}. Come back tomorrow, or add new words.`
              : `Add words and phrases in ${language.name} (or paste a list), and they'll come back here just before you'd forget them.`}
          </EmptyState>
        )}
        <div className="button-row lng-done-more">
          <button type="button" className="plain small" onClick={() => openPanel('langbulk', { languageId: language.language_id })}>Paste many cards</button>
        </div>
      </div>
    )
  }

  const learning = queue.filter((c) => c.state !== 'new' && c.state !== 'review').length
  const fresh = queue.filter((c) => c.state === 'new').length
  return (
    <div className="lng-review">
      <div className="lng-review-top">
        <p className="lng-counts" aria-label={`${fresh} new, ${learning} learning, ${queue.length - fresh - learning} to review`}>
          <span className="lng-count-new">{fresh} new</span> · <span className="lng-count-learn">{learning} learning</span> ·{' '}
          <span className="lng-count-due">{queue.length - fresh - learning} review</span></p>
        {modeBar}
      </div>
      <article className="card lng-card" aria-live="polite">
        <p className="muted small lng-ask">{cloze ? 'Fill the gap' : asking === 'flip' ? `What does it mean?` : asking === 'type' ? `Say it in ${language.name}` : 'What did you hear?'}
          {card.state === 'new' && <span className="pill tint">New</span>}</p>
        {cloze ? (
          <p className="lng-front lng-cloze">{cloze.parts.map((p, i) => (p.text != null ? <span key={i}>{p.text}</span>
            : <span key={i} className={shown ? 'lng-gap-filled' : 'lng-gap'}>{shown ? p.answer : p.hint ? `(${p.hint})` : '____'}</span>))}</p>
        ) : asking === 'flip' ? (
          <p className="lng-front" lang={voice ?? undefined}>{card.front}</p>
        ) : asking === 'type' ? (
          <p className="lng-front lng-meaning">{card.back}</p>
        ) : null}
        {cloze && <p className="muted lng-cloze-meaning">{card.back}</p>}
        {(asking === 'listen' || asking === 'flip' || shown) && (
          <button type="button" className="secondary small lng-say" onClick={() => speak(sayText, voice) || showToast('This browser has no voice for it')}>
            {asking === 'listen' && !shown ? '▶ Play again' : '▶ Say it'}</button>
        )}
        {asking !== 'flip' && (
          <label className="field lng-typed">{asking === 'listen' ? 'Type what you heard' : cloze ? 'The missing word' : `In ${language.name}`}
            <input ref={input} value={typed} onChange={(e) => setTyped(e.target.value)} disabled={shown} autoComplete="off" autoCapitalize="off"
              spellCheck="false" lang={voice ?? undefined} />
          </label>
        )}
        {shown && (
          <div className="lng-answer">
            {check && <p className={`lng-verdict ${check.verdict}`}>{VERDICT[check.verdict]}{check.verdict !== 'right' && check.verdict !== 'empty' && typed ? `: you wrote "${typed}"` : ''}</p>}
            {!cloze && <p className="lng-answer-main">{asking === 'type' ? <span lang={voice ?? undefined}>{card.front}</span> : card.back}
              {asking === 'listen' && <span className="muted"> · <span lang={voice ?? undefined}>{card.front}</span></span>}</p>}
            {card.example && <p className="lng-example"><span lang={voice ?? undefined}>{card.example}</span>
              {card.example_meaning && <span className="muted"> - {card.example_meaning}</span>}</p>}
            {card.notes && <p className="small muted lng-notes">{card.notes}</p>}
          </div>
        )}
        <div className="lng-actions">
          {!shown ? (
            <button type="button" className="primary lng-show" onClick={reveal}>{asking === 'flip' || !typed.trim() ? 'Show the answer' : 'Check'}</button>
          ) : (
            <div className="lng-grades" role="group" aria-label="How well did you know it?">
              {GRADES.map(([g, label]) => (
                <button key={g} type="button" disabled={busy} onClick={() => grade(g)}
                  className={`lng-grade g${g}${check?.suggest === g ? ' lng-suggest' : ''}`}>
                  <span>{label}</span><span className="lng-when">{card.next?.[g]}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </article>
      <div className="button-row lng-review-foot">
        {last && <button type="button" className="plain small" onClick={undo}>Undo</button>}
        <button type="button" className="plain small" onClick={() => openPanel('langcard', { id: card.card_id })}>Edit this card</button>
        <span className="spacer" />
        <span className="muted small">{tally.answered > 0 && `${tally.answered} done · `}keys: Enter shows, 1-4 grade</span>
      </div>
    </div>
  )
}
