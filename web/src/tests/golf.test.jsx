// Golf's pages and panels (modules/golf) drawn with the API faked (answers shaped like api/tests/test_golf.py's): the
// dashboard, rounds, stats, courses, bag, practice; the scorecard typed in place sends only the holes changed; a new
// round starts on the phone; Home's tiles. No React warnings (a missing key, a bad prop) on the way.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api.js'
import { AppContext } from '../core/app-context.js'
import { BagView, PracticeView } from '../modules/golf/GolfBag.jsx'
import { CoursePanel, CoursesView, FindCoursePanel } from '../modules/golf/GolfCourses.jsx'
import { NewRoundPanel, RoundPanel } from '../modules/golf/GolfPanels.jsx'
import { StatsView } from '../modules/golf/GolfStats.jsx'
import { Dashboard, RoundsView } from '../modules/golf/GolfViews.jsx'
import { GolfTiles } from '../modules/golf/HomeTiles.jsx'

const navigated = vi.fn()
vi.mock('react-router', async (importOriginal) => ({ ...(await importOriginal()), useNavigate: () => navigated }))
vi.mock('../api.js', async (importOriginal) => {
  const real = await importOriginal()
  const names = ['golfLists', 'golfSettings', 'saveGolfSettings', 'golfFindCourses', 'importGolfCourse', 'golfCourses', 'golfCourse',
    'addGolfCourse', 'saveGolfHoles', 'golfClubs', 'golfStandardBag', 'updateGolfClub', 'golfPractice', 'golfRounds', 'golfRound',
    'addGolfRound', 'updateGolfRound', 'saveGolfScorecard', 'golfSummary', 'golfStats', 'golfHandicap']
  return { ...real, api: { ...real.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } }
})

const PARS = [4, 4, 3, 5, 4, 4, 3, 4, 5, 4, 3, 4, 5, 4, 4, 3, 5, 4]
const SI = [7, 11, 15, 1, 5, 13, 17, 3, 9, 8, 16, 2, 10, 6, 12, 18, 4, 14]
const green = [[-27.4473, 153.0200], [-27.4473, 153.0202], [-27.4471, 153.0202], [-27.4471, 153.0200], [-27.4473, 153.0200]]
const MAP = { line: [[-27.45, 153.02], [-27.4472, 153.0201]], green, tees: [[[-27.4501, 153.0199], [-27.4501, 153.0201], [-27.4499, 153.0201], [-27.4501, 153.0199]]],
  fairways: [], bunkers: [], water: [] }
const holes = (scored = 18) => PARS.map((par, i) => {
  const strokes = i < scored ? par + (i % 2) : null
  return { hole_no: i + 1, par, stroke_index: SI[i], metres: 300 + i, received: 1, strokes, putts: strokes ? 2 : null,
    fairway: par > 3 && strokes ? 'hit' : null, penalties: 0, sand: 0, first_putt_m: null, picked_up: false, entered: strokes != null,
    points: strokes ? par + 1 - strokes + 2 : null, adjusted: strokes, to_par: strokes ? strokes - par : null, gir: strokes ? strokes - 2 <= par - 2 : null,
    shots: 0, sg: null, map: i === 0 ? MAP : { green: null } }
})
const SG = { off_tee: { total: 0, holes: 0, per18: null }, approach: { total: 0, holes: 0, per18: null }, around_green: { total: 0, holes: 0, per18: null },
  putting: { total: -1.2, holes: 6, per18: -3.6 } }
const STATS = { holes: 18, putt_holes: 18, putts: 36, fairway_chances: 14, fairways: 9, left: 3, right: 2, gir_chances: 18, gir: 9, gir_putts: 18,
  scramble_chances: 9, scrambles: 2, sand_chances: 0, sand_saves: 0, three_putts: 0, penalties: 1, eagles: 0, birdies: 0, pars: 9, bogeys: 9,
  doubles: 0, worse: 0 }
const brief = (over = {}) => ({ round_id: 1, played_on: '2026-11-10', course_id: 1, course_name: 'Victoria Park', tee_name: 'Blue', tee_colour: '#2255cc',
  holes: holes(), format: 'Stableford', status: 'done', competition: 'Monthly medal', counts: true, daily_handicap: 15, gross: 81, to_par: 9, par: 72,
  points: 33, net: 66, entered: 18, of: 18, differential: 9, putts: 36, gir: 9, fairways: 9, fairway_chances: 14, counted: true, ...over })
const RATES = { holes: 54, fairways: 64.3, missed_left: 21.4, missed_right: 14.3, gir: 50, putts: 36, putts_per_gir: 2, scrambling: 22.2, sand_saves: null,
  three_putts: 0, penalties: 1, par3: 3.5, par4: 4.4, par5: 5.5, kinds: { eagles: 0, birdies: 0, pars: 27, bogeys: 27, doubles: 0, worse: 0 },
  sg: SG, plays_like: { fairways: -3.3, gir: 2.3, putts: 30, scrambling: 15, three_putts: -2, penalties: 4.6 }, rounds: 3, average: 81, best: 81,
  average_points: 33, best_points: 33 }
const BENCH = { fairways: 46.8, gir: 32.8, putts: 32.2, scrambling: 27.6, three_putts: 1.7, penalties: 1.4 }
const HCP = { estimate: 7, official: null, official_as_of: null, current: 7, source: 'estimate', used: [1], of: 3, best: 1, counting: 3, target: null, allowance: 0.93 }
const SUMMARY = { year: 2026, handicap: HCP, handicap_trend: [{ day: '2026-11-08', index: 7.4, round_id: 3 }, { day: '2026-11-10', index: 7, round_id: 1 },
  { day: '2026-11-10', index: 7, round_id: 2 }], rounds: 3, this_year: { rounds: 3, holes: 54, practice: { sessions: 2, minutes: 30 } },
  playing: [brief({ round_id: 9, status: 'playing', entered: 4, gross: null, to_par: null, points: 8 })], recent: [brief(), brief({ round_id: 2 })],
  best: [brief()], stats: RATES, target: 2, bench: BENCH, trend: [{ day: '2026-11-08', round_id: 3, gross: 82, to_par: 10, points: 32, nine: false, differential: 9.9, course: 'Victoria Park' },
    { day: '2026-11-10', round_id: 1, gross: 81, to_par: 9, points: 33, nine: false, differential: 9, course: 'Victoria Park' }], courses: 1, clubs: 13 }
const ROUND = { ...brief({ status: 'playing' }), tee_id: 5, rating: 71, slope: 125, course_holes: 18, handicap: 15.2, partners: null, notes: null,
  weather: { sky: 'Clear', icon: '☀️', max: 28.2, min: 18.1, rain_mm: 0 }, holes: holes(16), shots: [],
  totals: { par: 72, holes: 18, entered: 16, complete: false, gross: null, to_par: null, to_par_so_far: 8, strokes_so_far: 72, points: 30, net: null,
    adjusted_gross: null, differential: null, rating: 71, nine: false }, stats: STATS, sg: SG }
const TEE = { tee_id: 5, course_id: 1, name: 'Blue', colour: '#2255cc', gender: null, rating: 71, slope: 125, position: 0,
  lengths: Object.fromEntries(PARS.map((_, i) => [String(i + 1), 300 + i])), metres: 5553, daily_handicap: 8 }
const COURSE = { course_id: 1, name: 'Victoria Park', place: 'Herston, QLD', lat: -27.45, lon: 153.02, holes: 18, osm: 'way/990001', website: null, notes: null,
  par: 72, mapped: 1, rounds: 3, last_played: '2026-11-10', rated: 1, tees: [TEE],
  holes_list: PARS.map((par, i) => ({ hole_no: i + 1, par, stroke_index: SI[i], map: i === 0 ? MAP : null,
    you: { played: 3, average: par + 0.7, vs_par: 0.7, best: par, par_or_better: 33, points: 1.7 } })),
  you: { rounds: 3, best: 81, average: 81.3, best_points: 34 },
  recent: [{ round_id: 1, played_on: '2026-11-10', tee_name: 'Blue', holes: holes(), gross: 81, to_par: 9, points: 33 }] }
const CLUBS = [{ club_id: 1, name: 'Driver', kind: 'Driver', loft: 10.5, carry_m: 200, brand: null, in_bag: true, position: 0, notes: null,
  measured: { shots: 4, average: 210, median: 208, longest: 231, short: 195, long: 220 } },
{ club_id: 2, name: '7 iron', kind: 'Iron', loft: 31, carry_m: 135, brand: null, in_bag: true, position: 1, notes: null, measured: null },
{ club_id: 3, name: 'Putter', kind: 'Putter', loft: 3, carry_m: null, brand: null, in_bag: true, position: 2, notes: null, measured: null }]
const PRACTICE = { sessions: [{ practice_id: 1, practiced_on: '2026-11-12', kind: 'Putting', minutes: 30, balls: null, focus: 'Lag putts', drill: 'Ladder',
  made: 7, attempts: 10, notes: null }], year: { sessions: 1, minutes: 30, balls: 0 }, kinds: [{ kind: 'Putting', sessions: 1, minutes: 30 }],
drills: [{ drill: 'Ladder', times: 1, best_pct: 70, last_pct: 70, last: '7/10' }] }

let app
let errors
const draw = (ui) => render(<MemoryRouter><AppContext.Provider value={app}>{ui}</AppContext.Provider></MemoryRouter>)

beforeEach(() => {
  app = { refreshKey: 0, changed: vi.fn(), showToast: vi.fn(), openPanel: vi.fn(), openThing: vi.fn() }
  errors = vi.spyOn(console, 'error')
  api.golfLists.mockResolvedValue({ formats: ['Stableford', 'Stroke', 'Par', 'Ambrose', 'Social'], hole_sets: [], fairways: [], lies: [],
    club_kinds: ['Driver', 'Wood', 'Hybrid', 'Iron', 'Wedge', 'Putter'], practice_kinds: ['Range', 'Putting'], genders: ['Men', 'Women'] })
  api.golfSettings.mockResolvedValue({ official_handicap: null, official_as_of: null, allowance: 0.93, target_handicap: null, home_course_id: 1 })
  api.golfSummary.mockResolvedValue(SUMMARY)
  api.golfCourses.mockResolvedValue([{ ...COURSE, tees: 1, best: 81, average: 81.3 }])
  api.golfCourse.mockResolvedValue(COURSE)
  api.golfRounds.mockResolvedValue([brief(), brief({ round_id: 2, counted: false, holes: holes().slice(9), of: 9, gross: 41 })])
  api.golfRound.mockResolvedValue(ROUND)
  api.golfStats.mockResolvedValue({ ...RATES, target: 2, bench: BENCH, trend: SUMMARY.trend, front_vs_par: 4.5, back_vs_par: 4.5, points_trend: [32, 33] })
  api.golfHandicap.mockResolvedValue({ ...HCP, history: SUMMARY.handicap_trend, rounds: [brief()], need: null })
  api.golfClubs.mockResolvedValue(CLUBS)
  api.golfPractice.mockResolvedValue(PRACTICE)
})
afterEach(() => {
  expect(errors).not.toHaveBeenCalled()
  cleanup()
  vi.clearAllMocks()
  errors.mockRestore()
})

describe('golf pages', () => {
  it('shows the dashboard: the handicap (an estimate), a round to resume, plays like with the weakest marked', async () => {
    draw(<Dashboard />)
    expect(await screen.findByText('7.0')).toBeTruthy()
    expect(screen.getByText('estimate')).toBeTruthy()
    expect(screen.getByText(/Playing now: Victoria Park/)).toBeTruthy()
    expect(await screen.findByText(/Daily handicap at Victoria Park/)).toBeTruthy()
    expect(screen.getByText('Work on this').closest('tr').textContent).toContain('Putts a round')
    fireEvent.click(screen.getByRole('button', { name: 'Resume' }))
    expect(navigated).toHaveBeenCalledWith('/golf/play?round=9')
  })

  it('lists rounds with the ones that count, a nine marked', async () => {
    draw(<RoundsView />)
    expect(await screen.findAllByText('Counts')).toHaveLength(1)
    expect(screen.getByText('Back 9')).toBeTruthy()
  })

  it('shows stats, strokes gained and the handicap', async () => {
    draw(<StatsView />)
    expect(await screen.findByText('Strokes gained')).toBeTruthy()
    expect(screen.getByText('Putting')).toBeTruthy()
    expect(screen.queryByText('Off the tee')).toBeNull()          // no holes: not shown
    expect(await screen.findByText(/Your last 1 differential/)).toBeTruthy()
    expect(screen.getByLabelText('Official GA Handicap')).toBeTruthy()
  })

  it('shows courses, the bag and practice', async () => {
    draw(<CoursesView />)
    expect(await screen.findByText(/1 of 18 holes mapped/)).toBeTruthy()
    cleanup()
    draw(<BagView />)
    expect(await screen.findByText('210 m')).toBeTruthy()
    cleanup()
    draw(<PracticeView />)
    expect(await screen.findByText('7/10 (70%)')).toBeTruthy()
  })

  it("Home's tiles: the handicap and the last round; nothing before the first round", async () => {
    draw(<GolfTiles />)
    expect(await screen.findByText('Handicap (estimate)')).toBeTruthy()
    expect(screen.getByText('33 pts')).toBeTruthy()
    cleanup()
    api.golfSummary.mockResolvedValue({ ...SUMMARY, rounds: 0 })
    const { container } = draw(<GolfTiles />)
    await waitFor(() => expect(container.querySelector('.skeleton')).toBeNull())
    expect(container.textContent).toBe('')
  })
})

describe('golf panels', () => {
  it('the scorecard sends only the holes typed in, then the round can be finished', async () => {
    api.saveGolfScorecard.mockResolvedValue(ROUND)
    api.updateGolfRound.mockResolvedValue({ ...ROUND, status: 'done' })
    draw(<RoundPanel id={1} onClose={() => {}} />)
    const score = await screen.findByLabelText('Hole 17 score')
    fireEvent.change(score, { target: { value: '6' } })
    fireEvent.change(screen.getByLabelText('Hole 17 putts'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Hole 18 score'), { target: { value: 'P' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save card' }))
    await waitFor(() => expect(api.saveGolfScorecard).toHaveBeenCalled())
    expect(api.saveGolfScorecard.mock.calls[0]).toEqual([1, [
      { hole_no: 17, strokes: 6, picked_up: false, putts: 2, fairway: null, penalties: 0, sand: 0, first_putt_m: null },
      { hole_no: 18, strokes: null, picked_up: true, putts: null, fairway: null, penalties: 0, sand: 0, first_putt_m: null }]])
    fireEvent.click(await screen.findByRole('button', { name: 'Finish' }))           // 2 holes not in: asks first
    fireEvent.click(await screen.findByRole('button', { name: 'Finish' }))
    await waitFor(() => expect(api.updateGolfRound).toHaveBeenCalledWith(1, { status: 'done' }))
  })

  it('a new round starts on the phone from the last tees played', async () => {
    api.addGolfRound.mockResolvedValue({ round_id: 12 })
    const onClose = vi.fn()
    draw(<NewRoundPanel onClose={onClose} />)
    await waitFor(() => expect(screen.getByLabelText('Tees').value).toBe('5'))
    fireEvent.click(screen.getByRole('button', { name: 'Play now' }))
    await waitFor(() => expect(navigated).toHaveBeenCalledWith('/golf/play?round=12'))
    expect(api.addGolfRound.mock.calls[0][0]).toMatchObject({ course_id: 1, tee_id: 5, holes: '18', format: 'Stableford' })
    expect(onClose).toHaveBeenCalled()
  })

  it('a course: tees with the daily handicap, holes, a drawn hole', async () => {
    const { container } = draw(<CoursePanel id={1} onClose={() => {}} />)
    expect(await screen.findByText('Your home course')).toBeTruthy()
    expect(screen.getByLabelText('Hole 1 par').value).toBe('4')
    expect(container.querySelector('.golf-sketch-green')).toBeTruthy()
    expect(screen.getByText(/rating 71 \/ slope 125/)).toBeTruthy()
  })

  it('finding a course: Add imports it and opens it', async () => {
    api.golfFindCourses.mockResolvedValue({ place: 'Testville, QLD', courses: [{ osm: 'way/990001', name: 'Stand-in Golf Club', lat: -27.47, lon: 153.02,
      place: 'Testville, QLD', metres: 2300, course_id: null }] })
    api.importGolfCourse.mockResolvedValue(COURSE)
    const onClose = vi.fn()
    draw(<FindCoursePanel onClose={onClose} />)
    fireEvent.change(screen.getByLabelText('Town or suburb'), { target: { value: 'Testville' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Add' }))
    await waitFor(() => expect(app.openPanel).toHaveBeenCalledWith('golfcourse', { id: 1 }))
    expect(api.importGolfCourse).toHaveBeenCalledWith('way/990001')
    expect(onClose).toHaveBeenCalled()
  })
})
