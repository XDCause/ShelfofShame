import { BootIcon, TrophyIcon } from '../../components/icons.jsx'
import { GearView } from '../volleyball/VolleyballViews.jsx'
import HikePanel from './HikePanel.jsx'
import { Dashboard, HikesView, HikingTiles } from './HikingViews.jsx'

// Hiking: your hikes (api/app/hiking.py) - imported from AllTrails as GPX files (or any GPS app's),
// with distance, climb, times, per-km splits and the route worked out from the track - or logged by
// hand. Your hiking gear shares Volleyball's gear page and panel (gear.hobby = 'hiking'), with the
// hikes and km each piece has done. Pages live at /hiking/<path>; hikes show in Recent activity and on the calendar.
export default {
  id: 'hiking',
  name: 'Hiking',
  // its colour (pine: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#4f9e62',
  banner: { scene: 'peaks', seed: 19, extras: ['snow', 'birds'], tagline: 'The view is worth the climb.' },
  what: 'Hikes from AllTrails: distance, climb, routes and splits',
  Icon: BootIcon,
  home: { Tiles: HikingTiles },
  actions: [{ label: 'Log a hike', Icon: BootIcon, run: (app) => app.openPanel('hike', {}) }],
  panels: { hike: HikePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'hikes', label: 'Hikes', Icon: BootIcon, render: () => <HikesView /> },
    { path: 'gear', label: 'Gear', Icon: BootIcon, render: () => <GearView hobby="hiking" Icon={BootIcon} /> },
  ],
}
