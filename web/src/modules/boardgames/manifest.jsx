import { DiceIcon, TrophyIcon } from '../../components/icons.jsx'
import { BoardGamesTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const GamesView = part(() => import('./BoardGamesViews.jsx'), 'GamesView')
const PlaysView = part(() => import('./BoardGamesViews.jsx'), 'PlaysView')
const GamePanel = part(() => import('./GamePanel.jsx'))
const PlayPanel = part(() => import('./GamePanel.jsx'), 'PlayPanel')

// Board games: your collection and every time you played. Pages live at /boardgames/<path>.
// Plays show on the calendar; "played @Catan" in the journal offers to log one.
export default {
  id: 'boardgames',
  name: 'Board games',
  // its colour (berry: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#c0588a',
  banner: { scene: 'forest', seed: 12, time: 'blue', extras: ['fog'], tagline: 'Good games. Great company.' },
  what: 'Your games and every play',
  Icon: DiceIcon,
  home: { Tiles: BoardGamesTiles },
  actions: [{ label: 'Log a play', Icon: TrophyIcon, run: (app) => app.openPanel('play') }],
  panels: { boardgame: GamePanel, play: PlayPanel },
  pages: [
    { path: 'games', label: 'Games', Icon: DiceIcon, render: () => <GamesView /> },
    { path: 'plays', label: 'Plays', Icon: TrophyIcon, render: () => <PlaysView /> },
  ],
}
