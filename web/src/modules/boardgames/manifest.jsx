import { DiceIcon, TrophyIcon } from '../../components/icons.jsx'
import { BoardGamesTiles, GamesView, PlaysView } from './BoardGamesViews.jsx'
import GamePanel, { PlayPanel } from './GamePanel.jsx'

// Board games: your collection and every time you played. Pages live at /boardgames/<path>.
// Plays show on the calendar; "played @Catan" in the journal offers to log one.
export default {
  id: 'boardgames',
  name: 'Board games',
  // its colour (berry: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#c0588a',
  banner: { scene: 'forest', seed: 12, tagline: 'Good games. Great company.' },
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
