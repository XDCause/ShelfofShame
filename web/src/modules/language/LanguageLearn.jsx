import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { api } from '../../api.js'
import { LanguageIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { plural, speak } from './answers.js'
import { LanguagePicker } from './LanguageViews.jsx'
import { useLanguages } from './langParts.js'
import { check, englishAnswers, makeLesson, noteParts, orderRight, scoreOf, spanishAnswers } from './lessonMaker.js'

// Learn: the built-in course (api/app/language_course.py; content in api/app/data/courses). The path - units with
// their goal and progress, lessons as steps (done with the best score, the next one highlighted, later ones dimmed
// but open for a peek) and a big Continue - and, at ?lesson=<id>, the lesson itself: its notes, then the exercises
// lessonMaker.js makes from it, a progress bar, feedback after each (right / almost / not quite, with the answer),
// mistakes again at the end, and a finish screen (score, time, the cards it added to the deck).

export function LearnView() {
  const { languages, current, pick } = useLanguages()
  const [params] = useSearchParams()
  const lessonId = params.get('lesson')
  const wanted = Number(params.get('language')) || null
  useEffect(() => { if (wanted && languages?.some((l) => l.language_id === wanted) && current?.language_id !== wanted) pick(wanted) },
    [wanted, languages, current, pick])
  if (!languages) return <p className="muted loading">Loading...</p>
  if (!current) return <NoLanguage />
  if (lessonId) {
    return (
      <section className="page lng-page">
        <LessonPlayer key={`${current.language_id}-${lessonId}`} lang={current} lessonId={lessonId} />
      </section>
    )
  }
  return (
    <section className="page lng-page">
      <LanguagePicker languages={languages} current={current} pick={pick} />
      <CoursePath key={current.language_id} lang={current} />
    </section>
  )
}

function NoLanguage() {
  const { openPanel } = useApp()
  return (
    <section className="page lng-page">
      <EmptyState Icon={LanguageIcon} title="Learn a language" action="+ Add a language" onAction={() => openPanel('langlanguage', {})}>
        Lessons that teach you from nothing, a few minutes at a time - and every word you learn goes into your cards, so it
        comes back just before you'd forget it. Add a language to begin (Spanish has a course).
      </EmptyState>
    </section>
  )
}

const lessonLink = (id, languageId) => `/language/learn?lesson=${encodeURIComponent(id)}&language=${languageId}`

// ---------------------------------------------------------------- the path
function CoursePath({ lang }) {
  const { refreshKey, changed, showToast } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.languageCourse(lang.language_id).then(setData).catch((e) => setError(e.message)) }, [lang.language_id, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  if (!data.course) {
    const use = async (code) => {
      try {
        await api.updateLanguage(lang.language_id, { course: code })
        changed()
      } catch (e) {
        showToast(e.message)
      }
    }
    return (
      <section className="card lngc-none">
        <h2 className="home-card-title">No course for {lang.name}</h2>
        {data.available.length ? (
          <>
            <p>{data.missing ? `The ${data.missing} course isn't there any more. ` : ''}Courses there are:</p>
            <ul className="lngc-choices">
              {data.available.map((c) => (
                <li key={c.code}>
                  <span><strong>{c.name}</strong> <span className="muted small">{plural(c.units, 'unit')} · {plural(c.lessons, 'lesson')} · {c.levels.join(' / ')}</span></span>
                  <button type="button" className={c.code === data.suggested ? 'primary' : 'secondary'} onClick={() => use(c.code)}>
                    Follow it for {lang.name}</button>
                </li>
              ))}
            </ul>
            <p className="muted small">Your cards, log and the rest stay as they are: the course adds its words to your deck as you go.</p>
          </>
        ) : <p className="muted">There are no courses yet.</p>}
      </section>
    )
  }
  const next = data.next
  return (
    <>
      <section className="card lngc-head">
        <div className="lngc-head-text">
          <h2 className="home-card-title">{data.course.name} course</h2>
          <p className="muted small">{data.done} of {plural(data.total, 'lesson')} done · {data.course.levels.join(' / ')}</p>
          <div className="lng-meter-bar" role="progressbar" aria-label="Course progress" aria-valuemin={0} aria-valuemax={data.total} aria-valuenow={data.done}>
            <span style={{ width: `${(100 * data.done) / Math.max(1, data.total)}%` }} />
          </div>
        </div>
        {next ? (
          <Link className="button primary lngc-continue" to={lessonLink(next.id, lang.language_id)}>
            {data.done ? 'Continue' : 'Start'}: {next.title}<span className="lngc-continue-unit">Unit {next.unit} · {next.unit_title}</span>
          </Link>
        ) : <p className="lngc-all-done">Every lesson done. Your cards keep it all fresh.</p>}
      </section>
      {data.units.map((u) => <UnitCard key={u.unit} unit={u} languageId={lang.language_id} />)}
    </>
  )
}

function UnitCard({ unit, languageId }) {
  const complete = unit.done === unit.total
  return (
    <section className={`card lngc-unit${complete ? ' complete' : ''}`} aria-labelledby={`lngc-unit-${unit.unit}`}>
      <div className="lngc-unit-head">
        <h2 id={`lngc-unit-${unit.unit}`} className="home-card-title">Unit {unit.unit} · {unit.title}</h2>
        <span className="pill tint">{unit.cefr}</span>
      </div>
      <p className="lngc-goal">{unit.goal}</p>
      <p className="muted small">{unit.done} of {unit.total} lessons{complete ? ' - unit done' : ''}</p>
      <ol className="lngc-steps">
        {unit.lessons.map((x, i) => (
          <li key={x.id} className={`lngc-step${x.done ? ' done' : ''}${x.next ? ' next' : ''}${x.unlocked ? '' : ' locked'}`}>
            <Link to={lessonLink(x.id, languageId)} className="lngc-step-link"
              aria-label={`Lesson ${i + 1}: ${x.title} - ${x.done ? `done, best ${x.best}%` : x.next ? 'next' : x.unlocked ? 'not done yet' : 'locked (open it for a peek)'}`}>
              <span className="lngc-dot" aria-hidden="true">{x.done ? '✓' : i + 1}</span>
              <span className="lngc-step-title">{x.title}</span>
              <span className="lngc-step-state">{x.done ? `${x.best}%${x.times > 1 ? ` · ${x.times}×` : ''}` : x.next ? 'Next' : x.unlocked ? '' : 'Locked'}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}

// ---------------------------------------------------------------- the lesson
const VERDICTS = {
  right: 'Right!', accents: 'Right - mind the accents', typo: 'Almost - a typo', article: 'Almost - keep the article',
  slips: 'All matched', wrong: 'Not quite', empty: 'Not quite',
}
const ASK = {
  introduce: 'New', match: 'Tap the pairs', pick: 'What does it mean?', type: 'Write it in', listen: 'Type what you hear',
  order: 'Put the words in order', gap: 'Fill the gap', translate: 'Write it in English',
}
const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

function LessonPlayer({ lang, lessonId }) {
  const navigate = useNavigate()
  const { changed } = useApp()
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState('')
  const [stage, setStage] = useState('notes')       // notes -> run -> finish
  const [queue, setQueue] = useState([])
  const [at, setAt] = useState(0)
  const [firstTries, setFirstTries] = useState({})
  const [mistakes, setMistakes] = useState(0)
  const [feedback, setFeedback] = useState(null)
  const [result, setResult] = useState(null)
  const [saving, setSaving] = useState(false)
  const started = useRef(0)
  const continueRef = useRef(null)
  const voice = lang.voice
  const back = useCallback(() => navigate('/language/learn'), [navigate])

  useEffect(() => {
    api.languageLesson(lessonId).then((l) => {
      setLesson(l)
      setQueue(makeLesson(l, { seed: Math.floor(Math.random() * 2 ** 31), earlier: l.earlier }))
    }).catch((e) => setError(e.message))
    started.current = Date.now()
  }, [lessonId])

  const finish = useCallback(async (tries, slips) => {
    setStage('finish')
    setSaving(true)
    setError('')
    const seconds = Math.min(14400, Math.round((Date.now() - started.current) / 1000))
    try {
      const r = await api.finishLanguageLesson(lang.language_id, lessonId, { score: scoreOf(tries), mistakes: Math.min(1000, slips), seconds })
      setResult({ ...r, seconds })
      changed()
    } catch (e) {
      setError(e.message)
    }
    setSaving(false)
  }, [lang.language_id, lessonId, changed])

  const ex = queue[at]
  const answer = useCallback((r) => {
    if (!ex || feedback) return
    const key = ex.orig ?? ex.key
    if (!(key in firstTries)) setFirstTries((t) => ({ ...t, [key]: r.ok && r.clean !== false }))
    if (!r.ok) {
      setMistakes((m) => m + 1)
      setQueue((q) => [...q, { ...ex, key: `${ex.key}-again${q.length}`, orig: key }])       // (it comes back at the end)
    } else if (r.clean === false) setMistakes((m) => m + (r.slips ?? 1))
    setFeedback(r)
  }, [ex, feedback, firstTries])

  const next = useCallback(() => {
    setFeedback(null)
    if (at + 1 >= queue.length) finish(firstTries, mistakes)
    else setAt(at + 1)
  }, [at, queue.length, finish, firstTries, mistakes])

  // "Can't listen now": this lesson's listening exercises are left out (not counted either way)
  const skipListening = () => {
    const rest = queue.filter((e, i) => i < at || e.kind !== 'listen')
    setQueue(rest)
    setFeedback(null)
    if (at >= rest.length) finish(firstTries, mistakes)
  }

  // Enter checks, then continues (a typed answer's own form takes its Enter; [data-own-enter] buttons keep theirs)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Enter' || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || stage !== 'run') return
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || e.target.closest?.('[data-own-enter], aside.drawer')) return
      e.preventDefault()
      if (feedback) next()
      else document.querySelector('.lngc-play .lngc-check:not([disabled])')?.click()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [stage, feedback, next])

  useEffect(() => { if (feedback) continueRef.current?.focus() }, [feedback])

  if (error && stage !== 'finish') {
    return <div className="lngc-play"><p className="alert error">{error}</p><Link className="button secondary" to="/language/learn">Back to the course</Link></div>
  }
  if (!lesson) return <p className="muted loading">Loading...</p>

  const head = (
    <div className="lngc-top">
      <button type="button" className="plain lngc-quit" data-own-enter onClick={back} aria-label="Quit the lesson">✕</button>
      {stage === 'run' ? (
        <div className="lngc-bar" role="progressbar" aria-label="Lesson progress" aria-valuemin={0} aria-valuemax={queue.length} aria-valuenow={at}>
          <span style={{ width: `${(100 * at) / Math.max(1, queue.length)}%` }} />
        </div>
      ) : <p className="muted small lngc-where">Unit {lesson.unit} · {lesson.unit_title} · lesson {lesson.number} of {lesson.of}</p>}
    </div>
  )

  if (stage === 'notes') {
    return (
      <div className="lngc-play">
        {head}
        <article className="card lngc-notes">
          <h2>{lesson.title}</h2>
          {noteParts(lesson.notes).map((runs, i) => (
            <p key={i}>{runs.map((r, j) => (r.bold ? <strong key={j}>{r.text}</strong> : <span key={j}>{r.text}</span>))}</p>
          ))}
          <p className="muted small">{plural(lesson.items.length, 'new word')} and phrases, {plural(lesson.sentences.length, 'sentence')}.</p>
          <button type="button" className="primary lngc-check lngc-main" onClick={() => setStage('run')}>Start the lesson</button>
        </article>
      </div>
    )
  }

  if (stage === 'finish') {
    const score = scoreOf(firstTries)
    return (
      <div className="lngc-play">
        {head}
        <section className="card lngc-finish" role="status">
          <h2>Lesson done: {lesson.title}</h2>
          {saving && <p className="muted">Saving...</p>}
          {error && <><p className="alert error">{error}</p>
            <button type="button" className="secondary" onClick={() => finish(firstTries, mistakes)}>Try saving again</button></>}
          {result && (
            <>
              <dl className="lngc-figures">
                <div><dt>Score</dt><dd>{score}%</dd></div>
                <div><dt>Time</dt><dd>{mmss(result.seconds)}</dd></div>
                <div><dt>New cards</dt><dd>{result.added}</dd></div>
              </dl>
              <p className="lngc-added">{result.added
                ? `${plural(result.words, 'word')} and ${plural(result.sentences, 'sentence')} went into your ${lang.name} cards: they'll come back in your reviews.`
                : 'Its words are in your cards already.'}{result.unit_done ? ` Unit ${lesson.unit} done!` : ''}</p>
              <div className="button-row lngc-finish-actions">
                {result.next && <Link className="button primary lngc-main" to={lessonLink(result.next.id, lang.language_id)}>Next lesson: {result.next.title}</Link>}
                <Link className="button secondary lngc-main" to="/language/review">Review cards</Link>
                <Link className="button plain" to="/language/learn">Back to the course</Link>
              </div>
            </>
          )}
        </section>
      </div>
    )
  }

  const shown = feedback ? feedbackText(ex, feedback) : null
  return (
    <div className="lngc-play">
      {head}
      <article className="card lngc-ex" aria-labelledby="lngc-ask" data-kind={ex.kind} data-key={ex.key}>
        <p id="lngc-ask" className="lngc-ask">{ex.kind === 'type' ? `${ASK.type} ${lang.name}` : ASK[ex.kind]}{ex.orig && <span className="pill low">Again</span>}</p>
        <Exercise key={ex.key} ex={ex} voice={voice} langName={lang.name} locked={!!feedback} onAnswer={answer} onNext={next}
          onSkipListening={skipListening} />
      </article>
      {feedback && (
        <div className={`lngc-feedback ${feedback.ok ? (feedback.verdict === 'right' ? 'right' : 'almost') : 'wrong'}`} role="status">
          <div className="lngc-feedback-text">
            <p className="lngc-verdict">{VERDICTS[feedback.verdict] ?? 'Right!'}</p>
            {shown && <p className="lngc-shown">{shown}</p>}
          </div>
          <button ref={continueRef} type="button" className="primary lngc-main" onClick={next}>Continue</button>
        </div>
      )}
    </div>
  )
}

// What the feedback shows: the right answer (and what it means), unless you had it exactly.
function feedbackText(ex, f) {
  if (ex.kind === 'match') return f.slips ? `${plural(f.slips, 'slip')} on the way` : null
  const exact = f.verdict === 'right'
  switch (ex.kind) {
    case 'pick': return exact ? null : `${ex.item.es} = ${ex.item.en}`
    case 'type': case 'listen': return exact ? `${f.match} = ${ex.item.en}` : `${f.match ?? ex.item.es} = ${ex.item.en}`
    case 'order': case 'gap': return `${ex.sentence.es} = ${ex.sentence.en}`
    case 'translate': return exact ? null : `${f.match ?? ex.sentence.en}`
    default: return null
  }
}

function Say({ text, voice, slow = false, label }) {
  const { showToast } = useApp()
  return (
    <button type="button" className="secondary small lngc-say" data-own-enter
      onClick={() => speak(text, voice, slow ? 0.6 : 0.9) || showToast('This browser has no voice for it')}>{label ?? (slow ? '🐢 Slower' : '▶ Say it')}</button>
  )
}

function Exercise(props) {
  const { ex } = props
  if (ex.kind === 'introduce') return <Introduce {...props} />
  if (ex.kind === 'match') return <Match {...props} />
  if (ex.kind === 'pick' || ex.kind === 'gap') return <Choose {...props} />
  if (ex.kind === 'order') return <Order {...props} />
  return <Typed {...props} />
}

function Introduce({ ex, voice, onNext }) {
  const { item } = ex
  useEffect(() => { speak(item.es, voice) }, [item.es, voice])
  return (
    <>
      <p className="lngc-big" lang={voice ?? undefined}>{item.es}</p>
      <p className="lngc-meaning">{item.en}{item.gender && <span className="muted small"> ({item.gender === 'm' ? 'masculine' : 'feminine'})</span>}</p>
      {item.note && <p className="lngc-tip">{item.note}</p>}
      <Say text={item.es} voice={voice} />
      <button type="button" className="primary lngc-check lngc-main" onClick={onNext}>Continue</button>
    </>
  )
}

function Match({ ex, voice, locked, onAnswer }) {
  const [picked, setPicked] = useState(null)          // {side, text}
  const [matched, setMatched] = useState([])         // es texts
  const [slips, setSlips] = useState(0)
  const [wrong, setWrong] = useState(null)
  const pairOf = (es) => ex.pairs.find((p) => p.es === es)
  const tap = (side, text) => {
    if (locked) return
    if (side === 'es') speak(text, voice)
    if (!picked || picked.side === side) { setPicked({ side, text }); return }
    const es = side === 'es' ? text : picked.text
    const en = side === 'en' ? text : picked.text
    setPicked(null)
    if (pairOf(es)?.en === en) {
      const done = [...matched, es]
      setMatched(done)
      setWrong(null)
      if (done.length === ex.pairs.length) onAnswer({ ok: true, clean: slips === 0, verdict: slips ? 'slips' : 'right', slips })
    } else {
      setSlips((s) => s + 1)
      setWrong([es, en])
    }
  }
  const isMatched = (side, text) => matched.some((es) => (side === 'es' ? es === text : pairOf(es).en === text))
  const button = (side, text) => (
    <button key={text} type="button" lang={side === 'es' ? voice ?? undefined : undefined} disabled={isMatched(side, text)}
      aria-pressed={picked?.side === side && picked.text === text}
      className={`lngc-option${isMatched(side, text) ? ' matched' : ''}${wrong?.includes(text) ? ' slip' : ''}`}
      onClick={() => tap(side, text)}>{text}</button>
  )
  return (
    <div className="lngc-match">
      <div className="lngc-col" role="group" aria-label="In the language">{ex.left.map((t) => button('es', t))}</div>
      <div className="lngc-col" role="group" aria-label="In English">{ex.right.map((t) => button('en', t))}</div>
      <p className="muted small lngc-match-left" aria-live="polite">{ex.pairs.length - matched.length ? `${ex.pairs.length - matched.length} to go` : 'All matched'}</p>
    </div>
  )
}

// Pick the meaning, or fill the gap: options to choose from, then Check.
function Choose({ ex, voice, locked, onAnswer }) {
  const [choice, setChoice] = useState(null)
  const gap = ex.kind === 'gap'
  const right = gap ? ex.sentence.gap : ex.item.en
  useEffect(() => { if (!gap) speak(ex.item.es, voice) }, [gap, ex, voice])
  const go = () => onAnswer({ ok: choice === right, verdict: choice === right ? 'right' : 'wrong' })
  return (
    <>
      {gap ? (
        <>
          <p className="lngc-sentence" lang={voice ?? undefined}>{ex.before}<span className={`lngc-blank${locked ? ' filled' : ''}`}>{locked ? right : choice ?? '_____'}</span>{ex.after}</p>
          <p className="lngc-meaning">{ex.sentence.en}</p>
        </>
      ) : (
        <>
          <p className="lngc-big" lang={voice ?? undefined}>{ex.item.es}</p>
          <Say text={ex.item.es} voice={voice} />
        </>
      )}
      <div className="lngc-options" role="group" aria-label="Options">
        {ex.options.map((o) => (
          <button key={o} type="button" disabled={locked} aria-pressed={choice === o} lang={gap ? voice ?? undefined : undefined}
            className={`lngc-option${locked && o === right ? ' matched' : ''}${locked && choice === o && o !== right ? ' slip' : ''}`}
            onClick={() => setChoice(o)}>{o}</button>
        ))}
      </div>
      {!locked && <button type="button" className="primary lngc-check lngc-main" disabled={!choice} onClick={go}>Check</button>}
    </>
  )
}

function Order({ ex, voice, locked, onAnswer }) {
  const [row, setRow] = useState([])        // tile ids, in the order tapped
  const used = new Set(row)
  const text = (id) => ex.tiles.find((t) => t.id === id).text
  const go = () => {
    const ok = orderRight(row.map(text), ex.answer)
    onAnswer({ ok, verdict: ok ? 'right' : 'wrong' })
    if (ok) speak(ex.sentence.es, voice)
  }
  return (
    <>
      <p className="lngc-meaning lngc-prompt">{ex.sentence.en}</p>
      <div className="lngc-row" aria-label="Your sentence" role="group">
        {row.length === 0 && <span className="muted small">Tap the words below</span>}
        {row.map((id) => (
          <button key={id} type="button" className="lngc-tile" disabled={locked} lang={voice ?? undefined}
            onClick={() => setRow(row.filter((x) => x !== id))} aria-label={`${text(id)} (take it back)`}>{text(id)}</button>
        ))}
      </div>
      <div className="lngc-bank" role="group" aria-label="Words">
        {ex.tiles.map((t) => (
          <button key={t.id} type="button" className={`lngc-tile${used.has(t.id) ? ' used' : ''}`} disabled={locked || used.has(t.id)}
            lang={voice ?? undefined} onClick={() => setRow([...row, t.id])}>{t.text}</button>
        ))}
      </div>
      {!locked && <button type="button" className="primary lngc-check lngc-main" disabled={!row.length} onClick={go}>Check</button>}
    </>
  )
}

// Type it in the language (from its meaning), type what you hear, or translate a sentence into English.
function Typed({ ex, voice, langName, locked, onAnswer, onSkipListening }) {
  const [typed, setTyped] = useState('')
  const input = useRef(null)
  const listen = ex.kind === 'listen'
  const english = ex.kind === 'translate'
  const thing = english ? ex.sentence : ex.item
  useEffect(() => {
    if (listen) speak(thing.es, voice)
    input.current?.focus()
  }, [listen, thing.es, voice])
  const go = (e) => {
    e.preventDefault()
    if (locked || !typed.trim()) return
    const r = english ? check(typed, englishAnswers(thing)) : check(typed, spanishAnswers(thing), { articles: true })
    onAnswer({ ...r, ok: r.ok })
  }
  return (
    <form className="lngc-typed" onSubmit={go}>
      {english ? (
        <>
          <p className="lngc-sentence" lang={voice ?? undefined}>{thing.es}</p>
          <Say text={thing.es} voice={voice} />
        </>
      ) : listen ? (
        <div className="button-row lngc-listen">
          <Say text={thing.es} voice={voice} label="▶ Play" />
          <Say text={thing.es} voice={voice} slow />
        </div>
      ) : <p className="lngc-big">{thing.en}</p>}
      <label className="field">{english ? 'In English' : listen ? 'What you heard' : `In ${langName}`}
        <input ref={input} value={typed} onChange={(e) => setTyped(e.target.value)} disabled={locked} autoComplete="off"
          autoCapitalize="off" spellCheck="false" lang={english ? 'en' : voice ?? undefined} />
      </label>
      {!locked && <button type="submit" className="primary lngc-check lngc-main" disabled={!typed.trim()}>Check</button>}
      {listen && !locked && <button type="button" className="plain small lngc-skip" data-own-enter onClick={onSkipListening}>Can't listen now</button>}
    </form>
  )
}
