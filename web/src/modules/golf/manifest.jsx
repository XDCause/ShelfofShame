import { GolfIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { GolfTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const Dashboard = part(() => import('./GolfViews.jsx'), 'Dashboard')
const RoundsView = part(() => import('./GolfViews.jsx'), 'RoundsView')
const CoursesView = part(() => import('./GolfCourses.jsx'), 'CoursesView')
const StatsView = part(() => import('./GolfStats.jsx'), 'StatsView')
const BagView = part(() => import('./GolfBag.jsx'), 'BagView')
const PracticeView = part(() => import('./GolfBag.jsx'), 'PracticeView')
const PlayView = part(() => import('./GolfPlay.jsx'), 'PlayView')
const RoundPanel = part(() => import('./GolfPanels.jsx'), 'RoundPanel')
const NewRoundPanel = part(() => import('./GolfPanels.jsx'), 'NewRoundPanel')
const CoursePanel = part(() => import('./GolfCourses.jsx'), 'CoursePanel')
const FindCoursePanel = part(() => import('./GolfCourses.jsx'), 'FindCoursePanel')
const ClubPanel = part(() => import('./GolfBag.jsx'), 'ClubPanel')
const PracticePanel = part(() => import('./GolfBag.jsx'), 'PracticePanel')

// Golf (2026-11-17, from a look at 18Birdies, Hole19, Golfshot, TheGrint, Arccos, Shot Scope and Clippd): courses from
// OpenStreetMap with every hole drawn, a live round on the phone (GPS to the front / middle / back of the green, tap the
// map to measure, mark shots with a club, a score that waits for signal), Stableford and a GA Handicap estimate, the
// scorecard typed in after, stats with "plays like a ..." and strokes gained, club distances, practice and drills.
// api/app/golf.py, golf_rounds.py, golf_scores.py, golfmath.py, golf_map.py.
export default {
  id: 'golf',
  name: 'Golf',
  // its colour (fairway green: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#3f9b5a',
  banner: { scene: 'hills', seed: 18, extras: ['trees', 'clouds'], tagline: 'Every hole is a fresh start.' },
  what: 'Rounds, Stableford, your handicap, course maps and club distances',
  Icon: GolfIcon,
  home: { Tiles: GolfTiles },
  actions: [{ label: 'Start a round', Icon: GolfIcon, run: (app) => app.openPanel('golfnewround', {}) }],
  panels: { golfround: RoundPanel, golfnewround: NewRoundPanel, golfcourse: CoursePanel, golffind: FindCoursePanel,
            golfclub: ClubPanel, golfpractice: PracticePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'play', label: 'Play', Icon: GolfIcon, render: () => <PlayView /> },
    { path: 'rounds', label: 'Rounds', Icon: GolfIcon, render: () => <RoundsView /> },
    { path: 'courses', label: 'Courses', Icon: GolfIcon, render: () => <CoursesView /> },
    { path: 'stats', label: 'Stats', Icon: TrophyIcon, render: () => <StatsView /> },
    { path: 'bag', label: 'Bag', Icon: TargetIcon, render: () => <BagView /> },
    { path: 'practice', label: 'Practice', Icon: TargetIcon, render: () => <PracticeView /> },
  ],
}
