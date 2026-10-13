import { BallIcon, ShoeIcon, VideoIcon } from '../../components/icons.jsx'
import { GearPanel, VideoPanel, VolleyballGamePanel } from './VolleyballPanels.jsx'
import { GamesView, GearView, VideosView, VolleyballTiles } from './VolleyballViews.jsx'

// Volleyball: games and training (with results), your gear, and video links. Pages live at
// /volleyball/<path>. Game nights go on the calendar (a weekly event); each one there offers
// "Log the result", which records the game against that day.
export default {
  id: 'volleyball',
  name: 'Volleyball',
  what: 'Games, training, gear and videos',
  Icon: BallIcon,
  home: { Tiles: VolleyballTiles },
  actions: [{ label: 'Log volleyball', Icon: BallIcon, run: (app) => app.openPanel('volleyball', {}) }],
  panels: { volleyball: VolleyballGamePanel, gear: GearPanel, video: VideoPanel },
  pages: [
    { path: 'games', label: 'Games', Icon: BallIcon, render: () => <GamesView /> },
    { path: 'gear', label: 'Gear', Icon: ShoeIcon, render: () => <GearView /> },
    { path: 'videos', label: 'Videos', Icon: VideoIcon, render: () => <VideosView /> },
  ],
}
