import { BallIcon, ShoeIcon, VideoIcon, WhistleIcon } from '../../components/icons.jsx'
import { VolleyballTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const CoachNotePanel = part(() => import('./Coach.jsx'), 'CoachNotePanel')
const CoachView = part(() => import('./Coach.jsx'), 'CoachView')
const GearPanel = part(() => import('./GearPanel.jsx'), 'GearPanel')
const TeamPanel = part(() => import('./VolleyballPanels.jsx'), 'TeamPanel')
const VideoPanel = part(() => import('./VolleyballPanels.jsx'), 'VideoPanel')
const VolleyballGamePanel = part(() => import('./VolleyballPanels.jsx'), 'VolleyballGamePanel')
const GamesView = part(() => import('./VolleyballViews.jsx'), 'GamesView')
const GearView = part(() => import('./VolleyballViews.jsx'), 'GearView')
const VideosView = part(() => import('./VolleyballViews.jsx'), 'VideosView')

// Volleyball: games and training (with results), your gear, videos (clips, highlights) and Coach
// (drills, things to fix, positions). Pages live at
// /volleyball/<path>. Game nights go on the calendar (a weekly event); each one there offers
// "Log the result", which records the game against that day.
export default {
  id: 'volleyball',
  name: 'Volleyball',
  // its colour (sand and sun: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#d9a62e',
  banner: { scene: 'coast', seed: 6, extras: ['clouds', 'birds'], tagline: 'Serve, dig, spike, repeat.' },
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
