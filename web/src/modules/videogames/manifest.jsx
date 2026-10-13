import { GamepadIcon, TrophyIcon } from '../../components/icons.jsx'
import VideoGamePanel from './VideoGamePanel.jsx'
import { Dashboard, GamesView, VideoGamesTiles } from './VideoGamesViews.jsx'

// Video games: Steam achievement hunting, a dashboard for 100% runs. Pages live at
// /videogames/<path>. Data comes from the official Steam Web API (api/app/steam.py), synced daily.
export default {
  id: 'videogames',
  name: 'Video games',
  what: 'Steam achievements and 100% runs',
  Icon: GamepadIcon,
  home: { Tiles: VideoGamesTiles },
  panels: { videogame: VideoGamePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'games', label: 'Games', Icon: GamepadIcon, render: () => <GamesView /> },
  ],
}
