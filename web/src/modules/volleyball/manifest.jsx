import { BallIcon, ShoeIcon, VideoIcon, WhistleIcon } from '../../components/icons.jsx'
import { CoachNotePanel, CoachView } from './Coach.jsx'
import { GearPanel, TeamPanel, VideoPanel, VolleyballGamePanel } from './VolleyballPanels.jsx'
import { GamesView, GearView, VideosView, VolleyballTiles } from './VolleyballViews.jsx'

// Volleyball: games and training (with results), your gear, videos (clips, highlights) and Coach
// (drills, things to fix, positions). Pages live at
// /volleyball/<path>. Game nights go on the calendar (a weekly event); each one there offers
// "Log the result", which records the game against that day.
export default {
  id: 'volleyball',
  name: 'Volleyball',
  what: 'Games, training, videos, coaching notes and gear',
  Icon: BallIcon,
  home: { Tiles: VolleyballTiles },
  actions: [{ label: 'Log volleyball', Icon: BallIcon, run: (app) => app.openPanel('volleyball', {}) }],
  panels: { volleyball: VolleyballGamePanel, gear: GearPanel, video: VideoPanel, vbteam: TeamPanel, coachnote: CoachNotePanel },
  pages: [
    { path: 'games', label: 'Games', Icon: BallIcon, render: () => <GamesView /> },
    { path: 'videos', label: 'Videos', Icon: VideoIcon, render: () => <VideosView /> },
    { path: 'coach', label: 'Coach', Icon: WhistleIcon, render: () => <CoachView /> },
    { path: 'gear', label: 'Gear', Icon: ShoeIcon, render: () => <GearView /> },
  ],
}
