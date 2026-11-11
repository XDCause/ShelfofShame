import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { useShared } from '../../core/useShared.js'
import { DIFFICULTIES, seedOf, sym } from './engine.js'

// Pieces the Sudoku pages share: making a puzzle (in a worker), the daily puzzle, settings kept on this device, the
// game played offline, times as text.

export const useSudokuSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`sudoku-summary-${refreshKey}`, () => api.sudokuSummary())
}

export const DIFF_TONE = { Easy: 'ok', Medium: 'teal', Hard: 'low', Expert: 'purple', Extreme: 'out' }

// 0:42 / 12:05 / 1:02:03
export const clockText = (s) => {
  if (s == null) return '—'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`
}

// The daily puzzle's difficulty by the day of the week: easy Monday, building to Expert at the weekend.
const DAILY = ['Expert', 'Easy', 'Medium', 'Medium', 'Hard', 'Hard', 'Expert']
export const dailyDifficulty = (iso) => DAILY[new Date(`${iso}T12:00:00`).getDay()]

// Make a puzzle in a Web Worker (engine.js generate): {difficulty} or {technique}, and for the daily one a seed from the
// date (the same day makes the same puzzle). onTries(n) hears how it's going.
export function makePuzzle({ size = 9, variant = 'classic', difficulty, technique = null, seed = null, budgetMs = size === 9 ? 8000 : 30000 }, onTries) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' })
    worker.onmessage = (e) => {
      if (e.data.tries) onTries?.(e.data.tries)
      if (e.data.done) { worker.terminate(); resolve(e.data.done) }
    }
    worker.onerror = (e) => { worker.terminate(); reject(new Error(e.message || "Couldn't make a puzzle.")) }
    worker.postMessage({ size, variant, difficulty, technique, seed, budgetMs })
  })
}

export const dailySeed = (iso) => seedOf(`off-the-clock-daily-${iso}`)
// The weekly puzzle (user, 2026-11-11: "a normal 9 x 9 Extreme"): one from the app's refined hardest list (weekly.js),
// taken in order a week at a time from the first Monday the weekly ran - give it a few sittings.
export const mondayOf = (iso) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return d.toLocaleDateString('en-CA') }
export const weeklySeed = (monday) => seedOf(`off-the-clock-weekly-${monday}`)
export const weeklyNumber = (monday) => Math.round((new Date(`${monday}T12:00:00`) - new Date('2026-11-09T12:00:00')) / (7 * 86400000))
export const eventSeed = (key, stop) => seedOf(`off-the-clock-event-${key}-${stop}`)

// Papers you might type a puzzle in from (only their names: the app never fetches their puzzles - they're licensed and
// paywalled - and you can type any other). Links open the paper's own puzzle page where it has a free one.
export const PAPERS = ['The Courier-Mail', 'The Sydney Morning Herald', 'The Age', 'The Australian', 'The New Daily',
  'The New York Times', 'The Guardian', 'The Times', 'The Daily Telegraph']
export const PAPER_LINKS = [['The New York Times', 'https://www.nytimes.com/puzzles/sudoku'],
  ['The New Daily (free, Australian)', 'https://thenewdaily.com.au/puzzles/quiz-sudoku/']]

// What a made puzzle becomes when it's saved.
export const gameData = (made, extra = {}) => ({
  puzzle: made.puzzle.map(sym).join(''), solution: made.solution.map(sym).join(''), difficulty: made.grade.difficulty, size: made.grade.size, variant: made.grade.variant ?? 'classic',
  techniques: made.grade.techniques, hardest: made.grade.hardest, ...extra,
})

// Settings on this device (they're about how you like to play, not data).
const SETTINGS_KEY = 'otc-sudoku-settings'
export const DEFAULT_SETTINGS = { mistakes: 'answer', autoNotes: true, sameDigit: true, timer: true, theme: 'classic' }
export const readSettings = () => {
  try { return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? '{}') } } catch { return { ...DEFAULT_SETTINGS } }
}
export const saveSettings = (s) => { try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(s)) } catch { /* fine without */ } }

// A game played while the PC couldn't be reached (the offline copy): kept on this device until it can be saved.
const LOCAL_KEY = 'otc-sudoku-local'
export const readLocal = () => { try { return JSON.parse(localStorage.getItem(LOCAL_KEY) ?? 'null') } catch { return null } }
export const saveLocal = (g) => { try { localStorage.setItem(LOCAL_KEY, JSON.stringify(g)) } catch { /* fine */ } }
export const clearLocal = () => { try { localStorage.removeItem(LOCAL_KEY) } catch { /* fine */ } }

// Saves a game kept on this device, once the server answers. Answers the saved game (or null).
export async function uploadLocal() {
  const g = readLocal()
  if (!g) return null
  const saved = await api.addSudokuGame({ ...g.data, state: g.state, seconds: g.seconds, mistakes: g.mistakes, hints: g.hints })
  if (g.solved) await api.saveSudokuGame(saved.game_id, { state: g.state, status: 'solved', hint_kinds: g.hintKinds ?? {} })
  else if (g.hintKinds) await api.saveSudokuGame(saved.game_id, { hint_kinds: g.hintKinds })
  clearLocal()
  return saved
}

export { DIFFICULTIES }
