import { BookIcon, GridIcon, MountainIcon, SparkleIcon, SudokuIcon, TrophyIcon } from '../../components/icons.jsx'
import { SudokuTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages: loaded when first shown (modules/lazy.js)
const TodayView = part(() => import('./SudokuViews.jsx'), 'TodayView')
const PlayView = part(() => import('./PlayView.jsx'), 'PlayView')
const LearnView = part(() => import('./SudokuViews.jsx'), 'LearnView')
const StatsView = part(() => import('./SudokuViews.jsx'), 'StatsView')
const AwardsView = part(() => import('./Awards.jsx'), 'AwardsView')
const EventsView = part(() => import('./EventsView.jsx'), 'EventsView')

// Sudoku (2026-11-11): puzzles made, graded and explained in the browser (engine.js - no puzzle site, and it works in
// the offline copy), a daily puzzle, hints that name the technique and teach it, practice for each technique, puzzles
// typed in from a book, 9 x 9 or a 16 x 16 giant, your times and achievements (api/app/sudoku.py keeps the games).
// Solves show on the calendar.
export default {
  id: 'sudoku',
  name: 'Sudoku',
  // its colour (a calm blue: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx)
  hue: '#5b7fd6',
  banner: { scene: 'peaks', seed: 41, time: 'dawn', extras: ['lake', 'clouds'], tagline: 'One digit at a time.' },
  what: 'Puzzles at every level, a daily one, hints that teach, your times',
  Icon: SudokuIcon,
  home: { Tiles: SudokuTiles },
  actions: [
    { label: 'Play sudoku', Icon: SudokuIcon, run: (app) => app.navigate('/sudoku/today') },
  ],
  panels: {},
  pages: [
    { path: 'today', label: 'Today', Icon: TrophyIcon, render: () => <TodayView /> },
    { path: 'play', label: 'Play', Icon: SudokuIcon, render: () => <PlayView /> },
    { path: 'events', label: 'Events', Icon: MountainIcon, render: () => <EventsView /> },
    { path: 'learn', label: 'Learn', Icon: BookIcon, render: () => <LearnView /> },
    { path: 'stats', label: 'Stats', Icon: GridIcon, render: () => <StatsView /> },
    { path: 'awards', label: 'Awards', Icon: SparkleIcon, render: () => <AwardsView /> },
  ],
}
