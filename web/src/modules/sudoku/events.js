// Sudoku events (2026-11-11): a winding path of puzzles, each stop opening when the one before is solved, with things to
// earn along the way (board themes; finishing a path is an achievement). Each stop's puzzle is made from a seed of the
// event and the stop, so it's the same puzzle whenever it's made. api/app/sudoku.py EVENTS has the same keys and lengths.
//   stops(n) -> [{stop, name, size, difficulty, reward}]
import { HARDEST } from './hardest.js'

// Board themes: the classic look, and ones earned on the paths and the Hardest 100. (28-sudoku.css: .sdk-theme-<key>)
export const THEMES = [
  { key: 'classic', name: 'Classic', how: 'Always yours' },
  { key: 'paper', name: 'Newsprint', how: 'The Grand Tour, stop 5' },
  { key: 'forest', name: 'Forest', how: 'The Grand Tour, stop 12' },
  { key: 'dusk', name: 'Dusk', how: 'The Grand Tour, stop 20' },
  { key: 'gold', name: 'Gold leaf', how: 'Finish The Grand Tour' },
  { key: 'glacier', name: 'Glacier', how: 'Patagonia Trail, stop 8' },
  { key: 'torres', name: 'Torres at dawn', how: 'Patagonia Trail, stop 16' },
  { key: 'condor', name: 'Condor', how: 'Finish the Patagonia Trail' },
  { key: 'holly', name: 'Holly', how: 'Advent calendar, 12 December' },
  { key: 'snowfall', name: 'Snowfall', how: 'Finish an Advent calendar' },
  { key: 'obsidian', name: 'Obsidian', how: 'Solve 10 of the Hardest 100' },
  { key: 'ember', name: 'Ember', how: 'Solve 50 of the Hardest 100' },
]

const PATAGONIA = ['Punta Arenas', 'Strait of Magellan', 'Puerto Natales', 'Cueva del Milodón', 'Laguna Amarga', 'Lago Pehoé',
  'Salto Grande', 'Mirador Cuernos', 'Lago Nordenskjöld', 'Valle del Francés', 'Mirador Británico', 'Refugio Los Cuernos',
  'Refugio Chileno', 'Base de las Torres', 'Lago Grey', 'Grey Glacier', 'Paine Grande', 'Cerro Castillo', 'El Calafate',
  'Perito Moreno Glacier', 'El Chaltén', 'Laguna Capri', 'Laguna Torre', 'Laguna de los Tres', 'Fitz Roy']

// A path's difficulty climbs: [up to stop, difficulty, size]
const ramp = (steps) => (stop) => steps.find(([upTo]) => stop <= upTo)

export const EVENTS = [
  {
    key: 'grand-tour', name: 'The Grand Tour', always: true, length: 30,
    art: { scene: 'hills', seed: 51, time: 'golden', extras: ['clouds', 'birds', 'trees'], hue: '#5b7fd6' }, layout: 'snake',
    blurb: 'Thirty stops from gentle to fierce, open all year. A 16 × 16 waits at stops 15 and 25.',
    level: ramp([[6, 'Easy', 9], [12, 'Medium', 9], [14, 'Hard', 9], [15, 'Medium', 16], [20, 'Hard', 9], [24, 'Expert', 9],
      [25, 'Hard', 16], [29, 'Expert', 9], [30, 'Extreme', 9]]),
    name_of: (stop) => `Stop ${stop}`,
    rewards: { 5: 'paper', 12: 'forest', 20: 'dusk', 30: 'gold' },
  },
  {
    key: 'patagonia-trail', name: 'Patagonia Trail', from: '2026-12-01', to: '2027-01-31', length: 25,
    art: { scene: 'peaks', seed: 25, time: 'dawn', extras: ['snow', 'lake', 'clouds'], hue: '#4f9ec4' }, layout: 'switchback',
    blurb: 'For the trip: 25 stops from Punta Arenas to Fitz Roy. Open 1 December to 31 January.',
    level: ramp([[4, 'Easy', 9], [9, 'Medium', 9], [14, 'Hard', 9], [16, 'Medium', 16], [21, 'Expert', 9], [24, 'Hard', 16], [25, 'Extreme', 9]]),
    name_of: (stop) => PATAGONIA[stop - 1],
    rewards: { 8: 'glacier', 16: 'torres', 25: 'condor' },
  },
]
// The Advent calendar: 24 stops, stop n opening on n December, made fresh each year (advent-<year>). Shown from
// November (the coming one) to January (the one just gone).
export function advent(year) {
  const day = (n) => `${year}-12-${String(n).padStart(2, '0')}`
  return {
    key: `advent-${year}`, name: `Advent calendar ${year}`, from: day(1), to: `${year}-12-31`, length: 24, opens: day,
    art: { scene: 'night', seed: year % 97, time: 'blue', extras: ['moon', 'snow', 'trees'], hue: '#7a5bd6' }, layout: 'garland',
    blurb: 'A puzzle a day from 1 December to Christmas Eve, a little harder each week - one door opens each morning.',
    level: ramp([[6, 'Easy', 9], [12, 'Medium', 9], [18, 'Hard', 9], [23, 'Expert', 9], [24, 'Extreme', 9]]),
    name_of: (stop) => `${stop} December`,
    rewards: { 12: 'holly', 24: 'snowfall' },
  }
}
const now = new Date()
EVENTS.push(advent(now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()))
export const EVENT = new Proxy(Object.fromEntries(EVENTS.map((e) => [e.key, e])), {
  get: (known, key) => known[key] ?? (/^advent-\d{4}$/.test(key) ? advent(Number(key.slice(7))) : undefined),   // (an older year's)
})

export const stops = (event) => Array.from({ length: event.length }, (_, i) => {
  const [, difficulty, size] = event.level(i + 1)
  return { stop: i + 1, name: event.name_of(i + 1), difficulty, size, reward: event.rewards[i + 1] ?? null }
})

// Open now? (an event with dates is playable between them; one that has ended keeps what you solved)
export const eventOpen = (event, todayIso) => event.always || (todayIso >= event.from && todayIso <= event.to)

// Themes you've earned, from how far you've got: {sets: {key: {solved, furthest}}} (the summary).
export function earnedThemes(sets = {}) {
  const got = new Set(['classic'])
  for (const [key, s] of Object.entries(sets)) {
    const e = EVENT[key]
    if (!e) continue
    for (const [stop, theme] of Object.entries(e.rewards)) if ((s.furthest ?? 0) >= Number(stop)) got.add(theme)
  }
  const hardest = sets.hardest?.solved ?? 0
  if (hardest >= 10) got.add('obsidian')
  if (hardest >= 50) got.add('ember')
  return got
}

export { HARDEST }
