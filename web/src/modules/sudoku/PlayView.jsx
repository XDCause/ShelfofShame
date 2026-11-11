import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, today as todayIso } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../../core/app-context.js'
import Board from './Board.jsx'
import { DIFFICULTIES_FOR, SYMBOLS, TECHNIQUE, X_DIFFICULTIES, bit, engineFor, sym } from './engine.js'
import { DIFF_TONE, PAPERS, clockText, clearLocal, dailyDifficulty, dailySeed, eventSeed, gameData, makePuzzle, mondayOf, readLocal,
  readSettings, saveLocal, saveSettings, useSudokuSummary, weeklyNumber } from './sudokuParts.js'
import { WEEKLY } from './weekly.js'
import { AwardList } from './Awards.jsx'
import PhotoReader from './PhotoReader.jsx'
import { EVENT, HARDEST, THEMES, earnedThemes, stops } from './events.js'

// Sudoku > Play: a new game (pick a size and a difficulty), the daily puzzle, practising a technique, or a puzzle typed
// in from a book; then the game itself - the board, notes, undo, hints that teach, the timer, saved as you go.
//   /sudoku/play?game=12 (or game=local: one made while the PC couldn't be reached), ?new=Hard (&size=16), ?daily=1
//   (&day=2026-11-03: a past one), ?weekly=1, ?set=hardest&stop=7 (or an event's key), ?practice=x_wing, ?enter=1 (&size=16)
export function PlayView() {
  const params = new URLSearchParams(window.location.search)
  const key = window.location.search
  const id = params.get('game')
  const size = params.get('size') === '16' ? 16 : 9
  const variant = params.get('variant') === 'x' && size === 9 ? 'x' : 'classic'
  if (id) return <GameLoader key={key} id={id} />
  if (params.get('new') || params.get('daily') || params.get('practice') || params.get('weekly') || params.get('set')) {
    return <Maker key={key} size={size} variant={variant} difficulty={params.get('new')} daily={params.get('daily') === '1'} day={params.get('day')}
      weekly={params.get('weekly') === '1'} set={params.get('set')} stop={Number(params.get('stop')) || 0} practice={params.get('practice')} />
  }
  if (params.get('enter')) return <EnterPuzzle key={key} size={size} />
  return <NewGame />
}

const ABOUT = { Easy: 'Singles, lots of clues', Medium: 'Singles and locked candidates', Hard: 'Pairs and triples',
  Expert: 'X-Wings, Swordfish, Y-Wings', Extreme: 'Beyond: chains and patience' }

function NewGame() {
  const [kind, setKind] = useState('9')                 // 9 / 16 / x
  const size = kind === '16' ? 16 : 9
  const extra = kind === '16' ? '&size=16' : kind === 'x' ? '&variant=x' : ''
  return (
    <section className="page sudoku">
      <section className="card home-card">
        <div className="section-head">
          <h2 className="home-card-title">New game</h2>
          <div className="segmented" role="group" aria-label="Kind">
            {[['9', '9 × 9'], ['x', 'Diagonal (X)'], ['16', '16 × 16']].map(([k, label]) => (
              <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{label}</button>))}
          </div>
        </div>
        {kind === 'x' && <p className="muted small">Diagonal (X) sudoku: both long diagonals must hold 1-9 once each too (they're shaded).
          A good way to see the board differently.</p>}
        {size === 16 && <p className="muted small">The giant: 16 rows, columns and 4 × 4 boxes, with the digits 1-9 then A-G (type the letters).
          Hard ones can take half a minute to make.</p>}
        <div className="sdk-pick">
          {(kind === 'x' ? X_DIFFICULTIES : DIFFICULTIES_FOR[size]).map((d) => (
            <Link key={d} className={`sdk-pick-btn ${DIFF_TONE[d]}`} to={`/sudoku/play?new=${d}${extra}`}>
              <strong>{d}</strong><span className="muted small">{ABOUT[d]}</span>
            </Link>
          ))}
        </div>
        <div className="button-row">
          <Link className="button secondary" to="/sudoku/play?daily=1">Today's daily puzzle</Link>
          <Link className="button secondary" to={`/sudoku/play?enter=1${size === 16 ? '&size=16' : ''}`}>Type in a puzzle</Link>
          <Link className="button plain" to="/sudoku/learn">Practise a technique</Link>
        </div>
      </section>
    </section>
  )
}

// Makes the puzzle (a worker), saves it, then opens it. With the PC out of reach it's kept on this device instead.
function Maker({ size, variant, difficulty, daily, day: pastDay, weekly, set, stop, practice }) {
  const navigate = useNavigate()
  const { changed } = useApp()
  const [tries, setTries] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    const run = async () => {
      const day = pastDay && /^\d{4}-\d{2}-\d{2}$/.test(pastDay) && pastDay <= todayIso() ? pastDay : todayIso()
      const week = mondayOf(todayIso())
      const go = (id) => navigate(`/sudoku/play?game=${id}`, { replace: true })
      if (daily) {
        const had = pastDay ? (await api.sudokuDailies(400).catch(() => [])).find((g) => g.daily_on === day) : await api.sudokuDaily().catch(() => null)
        if (had) { go(had.game_id); return }
      }
      if (weekly) {
        const had = await api.sudokuWeekly().catch(() => null)
        if (had) { go(had.game_id); return }
      }
      if (set) {
        const had = (await api.sudokuSet(set).catch(() => ({})))[stop]
        if (had) { go(had.game_id); return }
      }
      let made
      if (set === 'hardest' || weekly) {                // one of the Hardest 100, or this week's: the puzzle is in a list
        const e9 = engineFor(9)
        const n = weeklyNumber(week)
        // the library (the community's hardest, if it's loaded on this PC): ranks 1-100 are the Hardest 100.
        // The weekly is Extreme, not world-class (user, 2026-11-11: "too hard - just extreme level, not top 1000 level"):
        // a 'weekly' list if one's loaded (load-sudoku-library.ps1 -List weekly), else the app's own (weekly.js).
        // The library's 'hardest' list is only for the Hardest 100.
        const lib = (await (weekly ? api.sudokuLibrary('weekly', 1, 100000) : api.sudokuLibrary('hardest', stop, stop))
          .catch(() => ({ puzzles: [] }))).puzzles ?? []
        const text = weekly ? (lib.length ? lib[((n % lib.length) + lib.length) % lib.length].puzzle : WEEKLY[((n % WEEKLY.length) + WEEKLY.length) % WEEKLY.length])
          : lib[0]?.puzzle ?? HARDEST[stop - 1]
        const puzzle = e9.parse(text)
        made = { puzzle, solution: e9.solve(puzzle), grade: { ...e9.grade(puzzle), difficulty: 'Extreme' } }
      } else {
        const where = set && stops(EVENT[set])[stop - 1]
        const want = daily ? { difficulty: dailyDifficulty(day), seed: dailySeed(day) }
            : where ? { difficulty: where.difficulty, size: where.size, seed: eventSeed(set, stop) }
              : practice ? { technique: practice } : { difficulty, size, variant }
        made = await makePuzzle(want, (n) => live && setTries(n))
      }
      const data = gameData(made, daily ? { source: 'daily', daily_on: day } : weekly ? { source: 'weekly', week_of: week }
        : set ? { source: 'set', set_key: set, set_stop: stop } : practice ? { source: 'practice', practice } : {})
      if (practice) {          // solved with easier steps up to the moment the technique is the next move (notes filled)
        const start = engineFor(9).practiceStart(made.puzzle, practice)
        if (start) data.state = { v: start.values.map(sym).join(''), n: start.cands }
      }
      try {
        const saved = await api.addSudokuGame(data)
        changed()
        if (live) navigate(`/sudoku/play?game=${saved.game_id}`, { replace: true })
      } catch (e) {
        if (e.status && e.status !== 503) throw e
        saveLocal({ data, state: null, seconds: 0, mistakes: 0, hints: 0, hintKinds: {}, closest: made.closest })
        if (live) navigate('/sudoku/play?game=local', { replace: true })
      }
    }
    run().catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  const what = daily ? (pastDay ? `the daily puzzle for ${pastDay}` : "today's puzzle") : weekly ? "this week's puzzle"
    : set === 'hardest' ? `number ${stop} of the Hardest 100` : set ? `${EVENT[set]?.name}, stop ${stop}` : practice ? `a puzzle that needs ${TECHNIQUE[practice]?.name ?? 'that technique'}`
    : `a ${difficulty} ${size === 16 ? '16 × 16 ' : variant === 'x' ? 'Diagonal (X) ' : ''}puzzle`
  return (
    <section className="page sudoku">
      <section className="card home-card sdk-making">
        {error ? <p className="alert error">{error}</p> : (
          <>
            <p><strong>Making {what}...</strong></p>
            <p className="muted small">Each one is checked to have exactly one answer, then solved step by step to grade it{tries > 1 ? ` (${tries} tried so far)` : ''}.</p>
          </>
        )}
      </section>
    </section>
  )
}

function GameLoader({ id }) {
  const [game, setGame] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (id === 'local') {
      const g = readLocal()
      if (!g) { setError('That game was saved, or is no longer on this device.'); return }
      setGame({ size: 9, ...g.data, game_id: null, state: g.state, seconds: g.seconds, mistakes: g.mistakes, hints: g.hints,
        hint_kinds: g.hintKinds ?? {}, status: g.solved ? 'solved' : 'playing', local: true })
      return
    }
    api.sudokuGame(id).then(setGame).catch((e) => setError(e.message))
  }, [id])
  if (error) return <section className="page sudoku"><p className="alert error">{error}</p><Link className="button secondary" to="/sudoku/play">New game</Link></section>
  if (!game) return <p className="muted loading">Loading...</p>
  return <Game key={game.game_id ?? 'local'} record={game} />
}

const digits = (s) => [...s].map((ch) => SYMBOLS.indexOf(ch))

// A key -> a digit: 1-9, and on a 16 x 16 the letters A-G for 10-16.
const keyDigit = (e, size) => {
  const code = /^(?:Digit|Numpad)([1-9])$/.exec(e.code)
  if (code) return Number(code[1])
  if (/^[1-9]$/.test(e.key)) return Number(e.key)
  if (size === 16 && /^[a-gA-G]$/.test(e.key)) return SYMBOLS.indexOf(e.key.toUpperCase())
  return 0
}

function Game({ record }) {
  const navigate = useNavigate()
  const { changed } = useApp()
  const size = record.size ?? 9
  const variant = record.variant ?? 'classic'
  const eng = engineFor(size, variant)
  const ds = Array.from({ length: size }, (_, i) => i + 1)
  const solution = useRef(digits(record.solution)).current
  const given = useRef(digits(record.puzzle).map(Boolean)).current
  const [values, setValues] = useState(() => digits(record.state?.v ?? record.puzzle))
  const [notes, setNotes] = useState(() => record.state?.n ?? new Array(size * size).fill(0))
  const [sel, setSel] = useState(null)
  const [noteMode, setNoteMode] = useState(false)
  const [past, setPast] = useState([])
  const [future, setFuture] = useState([])
  const [seconds, setSeconds] = useState(record.seconds ?? 0)
  const [paused, setPaused] = useState(false)
  const [mistakes, setMistakes] = useState(record.mistakes ?? 0)
  const [hints, setHints] = useState(record.hints ?? 0)
  const [hintKinds, setHintKinds] = useState(record.hint_kinds ?? {})
  const [hint, setHint] = useState(null)              // {step, level 1-2}
  const [status, setStatus] = useState(record.status)
  const [settings, setSettingsState] = useState(readSettings)
  const [saveError, setSaveError] = useState('')
  const [best, setBest] = useState(null)
  const [earned, setEarned] = useState([])
  const [lessonDone, setLessonDone] = useState(false)
  const [rated, setRated] = useState(null)
  const [moves, setMoves] = useState(() => record.state?.m ?? [])
  const [replay, setReplay] = useState(null)          // {at: moves shown, playing}
  const { data: summary } = useSudokuSummary()
  const themes = earnedThemes(summary?.sets)
  const finished = status !== 'playing'
  // Practice: the board starts where the technique is needed, so its lesson opens straight away (not counted as a hint).
  useEffect(() => {
    if (!record.practice || record.status !== 'playing' || record.hints) return
    const s = eng.hintFor(values, notes, solution)
    if (s.technique === record.practice) setHint({ step: s, level: 2, lesson: true })
  }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  const setSettings = (s) => { setSettingsState(s); saveSettings(s) }

  // ---- saving (a second after the last change; and when leaving). A finished game only takes its final save.
  const latest = useRef({})
  latest.current = { values, notes, seconds, mistakes, hints, hintKinds, moves }
  const over = useRef(record.status !== 'playing')
  const persist = useCallback(async (extra = {}) => {
    if (over.current && !extra.status) return null
    const l = latest.current
    const state = { v: l.values.map(sym).join(''), n: l.notes, m: l.moves.slice(-5000) }
    if (record.local) {
      saveLocal({ ...readLocal(), state, seconds: l.seconds, mistakes: l.mistakes, hints: l.hints, hintKinds: l.hintKinds, solved: extra.status === 'solved' })
      return null
    }
    try {
      const r = await api.saveSudokuGame(record.game_id, { state, seconds: l.seconds, mistakes: l.mistakes, hints: l.hints, hint_kinds: l.hintKinds, ...extra })
      setSaveError('')
      return r
    } catch (e) {
      setSaveError(e.status === 503 ? "Offline - your moves are saved when the PC answers again." : e.message)
      return null
    }
  }, [record.game_id, record.local])
  const dirty = useRef(false)
  useEffect(() => {
    if (finished) return undefined
    dirty.current = true
    const t = setTimeout(() => { dirty.current = false; persist() }, 1000)
    return () => clearTimeout(t)
  }, [values, notes, mistakes, hints, persist, finished])
  useEffect(() => () => { if (dirty.current) persist() }, [persist])
  useEffect(() => {                               // the time, now and then
    if (finished || paused) return undefined
    const t = setInterval(() => persist(), 20000)
    return () => clearInterval(t)
  }, [finished, paused, persist])

  // ---- the moves (for the replay and the mistake map): every digit that changes, with the time - however it changed
  const shown = useRef(values)
  useEffect(() => {
    const was = shown.current
    shown.current = values
    if (over.current) return
    const changes = values.flatMap((v, i) => (v !== was[i] ? [[latest.current.seconds, i, v]] : []))
    if (changes.length) setMoves((m) => [...m, ...changes])
  }, [values])

  // ---- the timer: runs while you're here and not paused
  useEffect(() => {
    if (finished || paused) return undefined
    const t = setInterval(() => { if (document.visibilityState === 'visible') setSeconds((s) => s + 1) }, 1000)
    return () => clearInterval(t)
  }, [finished, paused])

  // ---- moves
  const remember = () => { setPast((p) => [...p.slice(-200), { values, notes }]); setFuture([]) }
  const won = async (v) => {
    over.current = true
    latest.current.moves = [...moves, ...v.flatMap((x, i) => (x !== values[i] ? [[seconds, i, x]] : []))]   // (the last digit)
    setMoves(latest.current.moves)
    setStatus('solved')
    setSel(null)
    setHint(null)
    latest.current.values = v
    const saved = await persist({ status: 'solved' })
    if (record.local && !saved) return
    changed()
    if (saved?.new_awards?.length) setEarned(saved.new_awards)
    if (saved?.rating) setRated(saved.rating)
    const st = await api.sudokuStats().catch(() => null)
    const mine = (size === 16 ? st?.giant : st?.per_difficulty)?.find((p) => p.difficulty === record.difficulty)
    if (mine) setBest(mine)
  }
  const place = (d, asNote = noteMode) => {
    if (finished || paused || sel == null || given[sel] || !d || d > size) return
    if (asNote) {
      if (values[sel]) return
      remember()
      setNotes((n) => n.map((m, i) => (i === sel ? m ^ bit(d) : m)))
      return
    }
    remember()
    const nv = values.map((v, i) => (i === sel ? (v === d ? 0 : d) : v))
    if (nv[sel] && nv[sel] !== solution[sel]) setMistakes((m) => m + 1)
    setValues(nv)
    if (nv[sel]) {
      setNotes((n) => n.map((m, i) => (i === sel ? 0 : settings.autoNotes && eng.PEERS[sel].includes(i) ? m & ~bit(d) : m)))
    }
    setHint(null)
    if (nv.every((v, i) => v === solution[i])) won(nv)
  }
  const erase = () => {
    if (finished || sel == null || given[sel] || (!values[sel] && !notes[sel])) return
    remember()
    setValues((v) => v.map((x, i) => (i === sel ? 0 : x)))
    setNotes((n) => n.map((m, i) => (i === sel ? 0 : m)))
  }
  const fillNotes = () => {
    if (finished) return
    remember()
    setNotes(eng.candidates(values))
    setHint(null)
  }
  const undo = () => {
    if (!past.length || finished) return
    setFuture((f) => [{ values, notes }, ...f])
    const last = past.at(-1)
    setPast((p) => p.slice(0, -1))
    setValues(last.values)
    setNotes(last.notes)
  }
  const redo = () => {
    if (!future.length || finished) return
    setPast((p) => [...p, { values, notes }])
    const next = future[0]
    setFuture((f) => f.slice(1))
    setValues(next.values)
    setNotes(next.notes)
  }

  // ---- hints: 1) which technique and where to look, 2) the cells and why, 3) apply it
  const askHint = () => {
    if (finished || paused) return
    if (hint && hint.level < 2) { setHint({ ...hint, level: 2 }); return }
    if (hint) { applyHint(hint.step); return }
    const step = eng.hintFor(values, notes, solution)
    setHint({ step, level: step.technique === 'mistake' || step.technique === 'note_mistake' ? 2 : 1 })
    setHints((h) => h + 1)
    setHintKinds((k) => ({ ...k, [step.technique]: (k[step.technique] ?? 0) + 1 }))
  }
  const applyHint = (s) => {
    remember()
    if (hint?.lesson) setLessonDone(true)
    if (s.technique === 'mistake') {
      setValues((v) => v.map((x, i) => (s.cells.includes(i) ? 0 : x)))
    } else if (s.technique === 'note_mistake') {
      const c = eng.candidates(values)
      setNotes((n) => n.map((m, i) => (s.cells.includes(i) ? c[i] : m)))
    } else if (s.place) {
      const { cell, digit } = s.place
      const nv = values.map((v, i) => (i === cell ? digit : v))
      setValues(nv)
      setNotes((n) => n.map((m, i) => (i === cell ? 0 : eng.PEERS[cell].includes(i) ? m & ~bit(digit) : m)))
      setSel(cell)
      if (nv.every((v, i) => v === solution[i])) won(nv)
    } else {
      const c = eng.candidates(values)
      setNotes((n) => {
        const out = [...n]
        for (const e of s.eliminate) out[e.cell] = (out[e.cell] || c[e.cell]) & ~bit(e.digit)
        return out
      })
    }
    setHint(null)
  }

  const giveUp = async () => {
    if (!window.confirm('Give up and see the answer?')) return
    over.current = true
    setValues([...solution])
    setStatus('gave_up')
    setHint(null)
    if (!record.local) {
      const r = await api.saveSudokuGame(record.game_id, { status: 'gave_up', seconds }).catch(() => null)
      if (r?.rating) setRated(r.rating)
      changed()
    }
    else clearLocal()
  }
  const restart = () => {
    if (finished || !window.confirm('Clear your digits and notes and start this puzzle again?')) return
    remember()
    setValues(values.map((v, i) => (given[i] ? v : 0)))
    setNotes(new Array(size * size).fill(0))
    setHint(null)
  }

  // ---- the keyboard: digits (Shift = a note; A-G on a 16 x 16), arrows, Backspace, N notes, Z / Y undo / redo, H hint, P pause
  const keys = useRef(null)
  keys.current = (e) => {
    if (e.target.closest?.('input, textarea, select, [contenteditable]') || e.altKey) return
    const k = e.key
    if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); return }
    if ((e.ctrlKey || e.metaKey) && k.toLowerCase() === 'y') { e.preventDefault(); redo(); return }
    if (e.ctrlKey || e.metaKey) return
    const d = keyDigit(e, size)
    if (d) { e.preventDefault(); place(d, noteMode !== e.shiftKey); return }
    const move = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[k]
    if (move) {
      e.preventDefault()
      setSel((s) => {
        if (s == null) return 0
        const r = (eng.rowOf(s) + move[0] + size) % size, c = (eng.colOf(s) + move[1] + size) % size
        return r * size + c
      })
      return
    }
    if (k === 'Backspace' || k === 'Delete' || k === '0') { e.preventDefault(); erase(); return }
    if (k === 'n' || k === 'N') { setNoteMode((m) => !m); return }
    if (k === 'h' || k === 'H') { askHint(); return }
    if (k === 'p' || k === 'P') { setPaused((p) => !p); return }
    if (k === 'Escape') setHint(null)
  }
  useEffect(() => {
    const h = (e) => keys.current(e)
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
  useEffect(() => {          // the selected cell takes the keyboard focus (screen readers say where you are)
    if (sel != null) document.querySelectorAll('.sdk-play .sdk-cell')[sel]?.focus({ preventScroll: true })
  }, [sel])

  // ---- how each cell looks
  // "Show a wrong digit straight away" checks against the answer - only the wrong one is red, even when it clashes with a
  // right one (user, 2026-11-11: both 9s in a box were red, so the right one looked wrong). "Only clashes" marks both.
  const bad = settings.mistakes === 'conflicts' ? eng.conflicts(values) : new Set()
  const selDigit = sel != null ? values[sel] : 0
  const hintUnits = hint ? new Set(hint.step.units.flatMap((u) => eng.UNITS[u])) : new Set()
  const hintCells = hint && hint.level >= 2 ? new Set(hint.step.cells) : new Set()
  const hintElim = hint && hint.level >= 2 ? new Set(hint.step.eliminate.map((e) => `${e.cell}:${e.digit}`)) : new Set()
  const look = (i) => {
    const out = []
    if (sel != null && i !== sel && eng.PEERS[sel].includes(i)) out.push('peer')
    if (settings.sameDigit && selDigit && values[i] === selDigit && i !== sel) out.push('same')
    if (settings.sameDigit && selDigit && !values[i] && notes[i] & bit(selDigit)) out.push('same-note')
    if (!given[i] && values[i] && (settings.mistakes === 'answer' ? values[i] !== solution[i] : bad.has(i))) out.push('wrong')
    if (hintUnits.has(i)) out.push('hint-area')
    if (hintCells.has(i)) out.push('hint-cell')
    if (hint?.level >= 2 && hint.step.eliminate.some((e) => e.cell === i)) out.push('hint-elim')
    if (finished && status === 'gave_up' && !given[i]) out.push('revealed')
    return out
  }
  const left = (d) => size - values.filter((v) => v === d).length
  const replayLook = (i, at) => {
    const v = replayValues(record.puzzle, moves, at)[i]
    return [!given[i] && v && v !== solution[i] && 'wrong'].filter(Boolean)
  }
  const sizeText = size === 16 ? '16 × 16 ' : variant === 'x' ? 'Diagonal (X) ' : ''
  const title = record.daily_on ? `Daily sudoku · ${record.daily_on}` : record.week_of ? `The weekly · week of ${record.week_of}`
    : record.set_key === 'hardest' ? `Hardest 100 · number ${record.set_stop}`
      : record.set_key ? `${EVENT[record.set_key]?.name ?? record.set_key} · ${stops(EVENT[record.set_key] ?? { length: 0 })[record.set_stop - 1]?.name ?? `stop ${record.set_stop}`}`
        : record.paper ? `From ${record.paper}` : record.practice ? `Practising ${TECHNIQUE[record.practice]?.name ?? record.practice}` : `${record.difficulty} ${sizeText}sudoku`
  return (
    <section className={`page sudoku sdk-play${size === 16 ? ' giant' : ''}`}>
      <div className="sdk-top">
        <span className="sdk-title"><span className={`pill ${DIFF_TONE[record.difficulty]}`}>{record.difficulty}</span> <strong>{title}</strong></span>
        <span className="sdk-stats">
          {settings.timer && <span className="sdk-clock" aria-label={`Time ${clockText(seconds)}`}>{clockText(seconds)}</span>}
          <span className="muted small">{mistakes} mistake{mistakes === 1 ? '' : 's'} · {hints} hint{hints === 1 ? '' : 's'}</span>
          {!finished && <button type="button" className="plain small" onClick={() => setPaused((p) => !p)} aria-pressed={paused}>{paused ? 'Resume' : 'Pause'}</button>}
        </span>
      </div>
      {record.local && <p className="alert small sdk-local">Played on this device while the PC can't be reached - it's saved to the app when it answers again.</p>}
      <div className="sdk-layout">
        <div className="sdk-board-wrap">
          <Board size={size} variant={variant} values={replay ? replayValues(record.puzzle, moves, replay.at) : values}
            notes={replay ? new Array(size * size).fill(0) : notes} given={given} sel={replay ? moves[replay.at - 1]?.[1] ?? null : sel}
            onSelect={(i) => !finished && setSel(i)} look={replay ? (i) => replayLook(i, replay.at) : look}
            struck={(i, d) => hintElim.has(`${i}:${d}`)} hidden={paused && !finished} theme={themes.has(settings.theme) ? settings.theme : 'classic'} />
          {paused && !finished && (
            <div className="sdk-paused"><p><strong>Paused</strong></p><button type="button" className="primary" onClick={() => setPaused(false)}>Resume</button></div>
          )}
        </div>
        <div className="sdk-side">
          {finished && replay ? <Replay moves={moves} replay={replay} setReplay={setReplay} /> : finished ? <Finished status={status} seconds={seconds} mistakes={mistakes} hints={hints} record={record} best={best} earned={earned} rated={rated}
            onReplay={moves.length ? () => setReplay({ at: 0, playing: true }) : null}
            onNew={() => navigate(`/sudoku/play?new=${record.difficulty}${size === 16 ? '&size=16' : variant === 'x' ? '&variant=x' : ''}`)} /> : (
            <>
              <div className={`sdk-pad${size === 16 ? ' giant' : ''}`} role="group" aria-label={noteMode ? 'Notes' : 'Digits'}>
                {ds.map((d) => (
                  <button key={d} type="button" className={`sdk-key${noteMode ? ' note' : ''}`} disabled={!noteMode && left(d) === 0}
                    onClick={() => place(d)} aria-label={`${noteMode ? 'Note' : 'Place'} ${sym(d)}${left(d) ? ` (${left(d)} left)` : ' (all placed)'}`}>
                    <span className="sdk-key-digit">{sym(d)}</span><span className="sdk-key-left" aria-hidden="true">{left(d) || '✓'}</span>
                  </button>
                ))}
              </div>
              <div className="sdk-tools">
                <button type="button" className="secondary" onClick={undo} disabled={!past.length}>Undo</button>
                <button type="button" className="secondary" onClick={erase}>Erase</button>
                <button type="button" className={noteMode ? 'primary' : 'secondary'} aria-pressed={noteMode} onClick={() => setNoteMode((m) => !m)}>Notes {noteMode ? 'on' : 'off'}</button>
                <button type="button" className="secondary" onClick={fillNotes}>Fill notes</button>
                <button type="button" className="primary" onClick={askHint}>{!hint ? 'Hint' : hint.level < 2 ? 'Show me' : 'Apply'}</button>
              </div>
              {hint && <HintCard hint={hint} eng={eng} onShow={askHint} onClose={() => setHint(null)} />}
              {lessonDone && !hint && <p className="alert ok small">That's the {TECHNIQUE[record.practice]?.name}. The rest of the puzzle is yours -
                it may need it again (ask for a hint if you get stuck).</p>}
              <p className="muted small sdk-keys">Keys: {size === 16 ? '1-9 and A-G' : '1-9'} place (Shift = a note) · arrows move · Backspace erase · N notes · H hint · P pause · Ctrl+Z / Ctrl+Y undo / redo</p>
              <Fold title="Options">
                <label className="field small">Mistakes
                  <select value={settings.mistakes} onChange={(e) => setSettings({ ...settings, mistakes: e.target.value })}>
                    <option value="answer">Show a wrong digit straight away</option>
                    <option value="conflicts">Only show clashes (same digit twice)</option>
                    <option value="off">Don't show them</option>
                  </select></label>
                <label className="check small"><input type="checkbox" checked={settings.autoNotes} onChange={(e) => setSettings({ ...settings, autoNotes: e.target.checked })} /> Take a digit out of the notes it rules out</label>
                <label className="check small"><input type="checkbox" checked={settings.sameDigit} onChange={(e) => setSettings({ ...settings, sameDigit: e.target.checked })} /> Highlight the same digit</label>
                <label className="check small"><input type="checkbox" checked={settings.timer} onChange={(e) => setSettings({ ...settings, timer: e.target.checked })} /> Show the timer</label>
                <label className="field small">Board theme
                  <select value={themes.has(settings.theme) ? settings.theme : 'classic'} onChange={(e) => setSettings({ ...settings, theme: e.target.value })}>
                    {THEMES.map((th) => <option key={th.key} value={th.key} disabled={!themes.has(th.key)}>{th.name}{themes.has(th.key) ? '' : ` - ${th.how}`}</option>)}
                  </select></label>
                <div className="button-row">
                  <button type="button" className="plain small" onClick={restart}>Start again</button>
                  <button type="button" className="plain small destructive" onClick={giveUp}>Give up</button>
                </div>
              </Fold>
              {saveError && <p className="alert error small">{saveError}</p>}
            </>
          )}
        </div>
      </div>
    </section>
  )
}

// The board after the first `at` moves.
function replayValues(puzzle, moves, at) {
  const v = digits(puzzle)
  for (const [, cell, d] of moves.slice(0, at)) v[cell] = d
  return v
}

// The replay: every digit as you put it in (wrong ones red), at 1x / 4x / 16x, with a slider to jump about.
function Replay({ moves, replay, setReplay }) {
  const [speed, setSpeed] = useState(4)
  useEffect(() => {
    if (!replay.playing) return undefined
    if (replay.at >= moves.length) { setReplay({ ...replay, playing: false }); return undefined }
    const t = setTimeout(() => setReplay({ ...replay, at: replay.at + 1 }), 1200 / speed)
    return () => clearTimeout(t)
  }, [replay, speed, moves.length, setReplay])
  const now = moves[replay.at - 1]
  return (
    <section className="sdk-done sdk-replay" aria-label="Replay">
      <h2 className="home-card-title">Replay</h2>
      <p className="muted small">Move {replay.at} of {moves.length}{now ? ` · at ${clockText(now[0])}` : ''}</p>
      <input type="range" min="0" max={moves.length} value={replay.at} aria-label="Move"
        onChange={(e) => setReplay({ at: Number(e.target.value), playing: false })} />
      <div className="button-row">
        <button type="button" className="primary small" onClick={() => setReplay({ at: replay.at >= moves.length ? 0 : replay.at, playing: !replay.playing })}>
          {replay.playing ? 'Pause' : replay.at >= moves.length ? 'Play again' : 'Play'}</button>
        <div className="segmented" role="group" aria-label="Speed">
          {[1, 4, 16].map((s) => <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}×</button>)}
        </div>
        <button type="button" className="plain small" onClick={() => setReplay(null)}>Done</button>
      </div>
    </section>
  )
}

function HintCard({ hint, eng, onShow, onClose }) {
  const s = hint.step
  const t = TECHNIQUE[s.technique]
  const where = s.units.length ? `look at ${s.units.map(eng.unitName).join(' and ')}` : s.cells.length > 1 ? 'look at the highlighted cells' : ''
  if (hint.lesson && t) {
    const byDigit = {}
    for (const e of s.eliminate) (byDigit[sym(e.digit)] ??= []).push(eng.cellName(e.cell))
    return (
      <section className="sdk-hint sdk-lesson" aria-live="polite">
        <div className="section-head">
          <strong>Lesson: {s.name}</strong>
          <button type="button" className="icon-btn" aria-label="Close the lesson" onClick={onClose}>✕</button>
        </div>
        <p className="small muted">The easier steps are done for you and every cell's notes are filled in: this is the moment
          a {s.name} is the next move.</p>
        <ol className="sdk-lesson-steps small">
          <li><strong>The idea.</strong> {t.about}</li>
          <li><strong>Here.</strong> {s.text}</li>
          {s.eliminate.length > 0 && <li><strong>So it rules out:</strong> {Object.entries(byDigit).map(([d, cs]) => `${d} from ${cs.join(', ')}`).join('; ')} (crossed
            out in red on the board).</li>}
          {s.place && <li><strong>So:</strong> {eng.cellName(s.place.cell)} is {sym(s.place.digit)}.</li>}
        </ol>
        <div className="button-row">
          <button type="button" className="primary small" onClick={onShow}>Apply it</button>
          <Link className="button plain small" to={`/sudoku/learn#${s.technique}`}>More about the {s.name}</Link>
        </div>
      </section>
    )
  }
  return (
    <section className="sdk-hint" aria-live="polite">
      <div className="section-head">
        <strong>{s.name}</strong>
        <button type="button" className="icon-btn" aria-label="Close the hint" onClick={onClose}>✕</button>
      </div>
      {hint.level < 2 && t ? <p className="small">Try a <strong>{s.name}</strong>{where && ` - ${where}`}.</p> : <p className="small">{s.text}</p>}
      <div className="button-row">
        {t && <Link className="button plain small" to={`/sudoku/learn#${s.technique}`}>What's a {s.name}?</Link>}
        {s.technique !== 'mistake' && s.technique !== 'note_mistake' && hint.level < 2 && <button type="button" className="secondary small" onClick={onShow}>Show me</button>}
        {hint.level >= 2 && <button type="button" className="primary small" onClick={onShow}>{s.technique === 'mistake' ? 'Take them out' : s.technique === 'note_mistake' ? 'Fix the notes' : 'Apply'}</button>}
      </div>
    </section>
  )
}

function Finished({ status, seconds, mistakes, hints, record, best, earned, rated, onNew, onReplay }) {
  const event = record.set_key && EVENT[record.set_key]
  const nextStop = record.set_key && status === 'solved' && record.set_stop < (record.set_key === 'hardest' ? HARDEST.length : event?.length ?? 0) ? record.set_stop + 1 : null
  const reward = event?.rewards[record.set_stop] && status === 'solved' ? THEMES.find((th) => th.key === event.rewards[record.set_stop]) : null
  const newBest = best && status === 'solved' && best.best === seconds && best.solved > 1
  const easier = Object.keys(record.techniques ?? {}).length - 1
  return (
    <section className={`sdk-done ${status}`} aria-live="polite">
      <h2 className="home-card-title">{status === 'solved' ? 'Solved! 🎉' : 'The answer'}</h2>
      {status === 'solved' && (
        <p><strong className="sdk-done-time">{clockText(seconds)}</strong>
          <span className="muted small"> · {mistakes} mistake{mistakes === 1 ? '' : 's'} · {hints ? `${hints} hint${hints === 1 ? '' : 's'}` : 'no hints'}</span></p>
      )}
      {newBest && <p className="alert ok small">A new best for {record.difficulty}!</p>}
      {rated?.change != null && (
        <p className="sdk-rated"><strong className={rated.change >= 0 ? 'ok-text' : 'sdk-down'}>{rated.change >= 0 ? '+' : '−'}{Math.abs(rated.change)}</strong> rating
          {' '}→ <strong>{rated.now}</strong> <span className="pill tint">{rated.rank.name}</span>
          {rated.rank.next && <span className="muted small"> · {rated.rank.next.at - rated.now} to {rated.rank.next.name}</span>}</p>
      )}
      {reward && <p className="alert ok small">You've earned the <strong>{reward.name}</strong> board theme - pick it in Options.</p>}
      {best && !newBest && status === 'solved' && <p className="muted small">Your best {record.difficulty}: {clockText(best.best)} · average {clockText(best.average)} over {best.solved}</p>}
      {earned.length > 0 && (
        <div className="sdk-earned">
          <p><strong>Achievement{earned.length === 1 ? '' : 's'} unlocked!</strong></p>
          <AwardList awards={earned} compact />
        </div>
      )}
      {record.hardest && <p className="muted small">It needed: <Link to={`/sudoku/learn#${record.hardest}`}>{TECHNIQUE[record.hardest]?.name}</Link>
        {easier > 0 && ` (and ${easier} easier technique${easier === 1 ? '' : 's'})`}</p>}
      {onReplay && <button type="button" className="secondary small" onClick={onReplay}>▶ Watch the replay</button>}
      <div className="button-row">
        {nextStop ? <Link className="button primary" to={`/sudoku/play?set=${record.set_key}&stop=${nextStop}`}>On to {record.set_key === 'hardest' ? `number ${nextStop}` : `stop ${nextStop}`}</Link>
          : !record.set_key && !record.week_of && <button type="button" className="primary" onClick={onNew}>New {record.difficulty} game</button>}
        {record.set_key ? <Link className="button secondary" to="/sudoku/events">Back to the path</Link> : <Link className="button secondary" to="/sudoku/today">Today</Link>}
      </div>
    </section>
  )
}

// A puzzle from a book or a paper: type the clues on an empty board (or paste them, 0 or . for empty); it's checked for
// exactly one answer, graded, and saved.
function EnterPuzzle({ size }) {
  const navigate = useNavigate()
  const { changed } = useApp()
  const eng = engineFor(size)
  const cells = size * size
  const [values, setValues] = useState(new Array(cells).fill(0))
  const [sel, setSel] = useState(0)
  const [paste, setPaste] = useState('')
  const [paper, setPaper] = useState(new URLSearchParams(window.location.search).get('paper') ?? '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const put = (d) => setValues((v) => v.map((x, i) => (i === sel ? d : x)))
  useEffect(() => {
    const h = (e) => {
      if (e.target.closest?.('input, textarea')) return
      const d = keyDigit(e, size)
      if (d) { e.preventDefault(); put(d); setSel((s) => Math.min(cells - 1, s + 1)) }
      else if (e.key === 'Backspace' || e.key === 'Delete' || e.key === '0') { e.preventDefault(); put(0) }
      else {
        const m = { ArrowUp: -size, ArrowDown: size, ArrowLeft: -1, ArrowRight: 1 }[e.key]
        if (m) { e.preventDefault(); setSel((s) => Math.max(0, Math.min(cells - 1, s + m))) }
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })
  const minClues = size === 9 ? 17 : 55
  const start = async () => {
    setError('')
    if (values.filter(Boolean).length < minClues) { setError(`A ${size} × ${size} sudoku needs at least ${minClues} clues to have only one answer.`); return }
    setBusy(true)
    await new Promise((r) => setTimeout(r, 30))               // (let "Checking..." show: a 16 x 16 takes a moment)
    const n = eng.solveCount(values, 2)
    if (n === 0) { setError('That has no answer - check the digits you typed (a clash, or a typo).'); setBusy(false); return }
    if (n > 1) { setError('That has more than one answer, so it can only be solved by guessing. Check for a missing clue.'); setBusy(false); return }
    try {
      const g = eng.grade(values)
      const saved = await api.addSudokuGame({ puzzle: values.map(sym).join(''), solution: eng.solve(values).map(sym).join(''), difficulty: g.difficulty,
        size, techniques: g.techniques, hardest: g.hardest, source: 'typed', paper: paper.trim() || null })
      changed()
      navigate(`/sudoku/play?game=${saved.game_id}`, { replace: true })
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return (
    <section className={`page sudoku sdk-play${size === 16 ? ' giant' : ''}`}>
      <div className="sdk-layout">
        <div className="sdk-board-wrap">
          <Board size={size} values={values} notes={new Array(cells).fill(0)} given={values.map(Boolean)} sel={sel} onSelect={setSel} label="The puzzle you're typing in" />
        </div>
        <div className="sdk-side">
          <div className="section-head">
            <h2 className="home-card-title">Type in a puzzle</h2>
            <div className="segmented" role="group" aria-label="Size">
              {[9, 16].map((n) => <button key={n} type="button" aria-pressed={size === n} onClick={() => navigate(`/sudoku/play?enter=1${n === 16 ? '&size=16' : ''}`)}>{n} × {n}</button>)}
            </div>
          </div>
          <p className="muted small">Tap a cell and type its digit{size === 16 ? ' (A-G for 10-16)' : ''} - 0 or Backspace for empty, arrows move. Or paste it row by row, with 0 or . for the empty cells.</p>
          {size === 9 && <PhotoReader onRead={(g) => { setValues(g); setError('') }} />}
          <div className={`sdk-pad${size === 16 ? ' giant' : ''}`} role="group" aria-label="Digits">
            {Array.from({ length: size }, (_, i) => i + 1).map((d) => (
              <button key={d} type="button" className="sdk-key" onClick={() => { put(d); setSel((s) => Math.min(cells - 1, s + 1)) }} aria-label={`Put ${sym(d)}`}>
                <span className="sdk-key-digit">{sym(d)}</span></button>
            ))}
          </div>
          <div className="button-row"><button type="button" className="secondary" onClick={() => put(0)}>Clear the cell</button>
            <button type="button" className="plain" onClick={() => setValues(new Array(cells).fill(0))}>Clear all</button></div>
          <label className="field small">Paste {cells} characters
            <input value={paste} onChange={(e) => { setPaste(e.target.value); const g = eng.parse(e.target.value); if (g) setValues(g) }}
              placeholder={size === 9 ? '530070000600195000...' : '0FC08E07G05...'} /></label>
          <label className="field small">From (a newspaper or a book - optional)
            <input value={paper} onChange={(e) => setPaper(e.target.value)} list="sdk-papers" maxLength={80} placeholder="e.g. The Courier-Mail" /></label>
          <datalist id="sdk-papers">{PAPERS.map((x) => <option key={x} value={x} />)}</datalist>
          <p className="muted small">{values.filter(Boolean).length} clues</p>
          <button type="button" className="primary" disabled={busy} onClick={start}>{busy ? 'Checking...' : 'Check it and play'}</button>
          {error && <p className="alert error small">{error}</p>}
        </div>
      </div>
    </section>
  )
}
