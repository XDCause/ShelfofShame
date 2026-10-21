import { ChessIcon, GridIcon, TrophyIcon } from '../../components/icons.jsx'
import ChessGamePanel from './ChessGamePanel.jsx'
import { ChessTiles, Dashboard, GamesView, OpeningsView } from './ChessViews.jsx'

// Chess: your chess.com games (the official public API, api/app/chess.py - synced daily) and games
// over the board, logged by hand. Pages live at /chess/<path>; games show on the calendar (one
// line a day per time control) and can be mentioned in the journal.
export default {
  id: 'chess',
  name: 'Chess',
  // its colour (walnut: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#a8825a',
  banner: { scene: 'hills', seed: 14, time: 'blue', extras: ['moon', 'lake', 'trees'], tagline: 'One move at a time.' },
  what: 'chess.com ratings, games and openings; games over the board',
  Icon: ChessIcon,
  home: { Tiles: ChessTiles },
  actions: [{ label: 'Log a chess game', Icon: ChessIcon, run: (app) => app.navigate('/chess/games?add=1') }],
  panels: { chessgame: ChessGamePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'games', label: 'Games', Icon: ChessIcon, render: () => <GamesView /> },
    { path: 'openings', label: 'Openings', Icon: GridIcon, render: () => <OpeningsView /> },
  ],
}
