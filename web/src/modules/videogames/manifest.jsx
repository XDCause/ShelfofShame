import { GamepadIcon, GridIcon, TrophyIcon, UsersIcon } from '../../components/icons.jsx'
import { FriendPanel, FriendsView } from './Friends.jsx'
import FindGamePanel from './FindGamePanel.jsx'
import StatsView from './StatsView.jsx'
import VideoGamePanel from './VideoGamePanel.jsx'
import { Dashboard, GamesPage, VideoGamesTiles } from './VideoGamesViews.jsx'

// Video games: Steam achievement hunting, a dashboard for 100% runs. Pages live at
// /videogames/<path>. Data comes from the official Steam Web API (api/app/steam.py), synced daily;
// Epic and Ubisoft games come from the user's Exophase profile (api/app/othergames.py).
export default {
  id: 'videogames',
  name: 'Video games',
  // its colour (dusk violet: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#8f72d6',
  banner: { scene: 'night', seed: 9, extras: ['aurora'], tagline: 'Every achievement, every hour.' },
  what: 'Steam achievements and 100% runs',
  Icon: GamepadIcon,
  home: { Tiles: VideoGamesTiles },
  panels: { videogame: VideoGamePanel, findgame: FindGamePanel, vgfriend: FriendPanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'games', label: 'Games', Icon: GamepadIcon, render: () => <GamesPage /> },
    { path: 'stats', label: 'Stats', Icon: GridIcon, render: () => <StatsView /> },
    { path: 'friends', label: 'Friends', Icon: UsersIcon, render: () => <FriendsView /> },
  ],
}
