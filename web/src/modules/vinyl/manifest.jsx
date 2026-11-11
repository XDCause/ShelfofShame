import { ClockIcon, GearIcon, GridIcon, TrophyIcon, VinylIcon } from '../../components/icons.jsx'
import { VinylTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const RecordPanel = part(() => import('./RecordPanel.jsx'))
const AddRecordPanel = part(() => import('./vinylParts.jsx'), 'AddRecordPanel')
const Dashboard = part(() => import('./VinylViews.jsx'), 'Dashboard')
const CrateView = part(() => import('./VinylViews.jsx'), 'CrateView')
const PlaysView = part(() => import('./VinylViews.jsx'), 'PlaysView')
const StatsView = part(() => import('./VinylViews.jsx'), 'StatsView')
const ConnectView = part(() => import('./VinylViews.jsx'), 'ConnectView')

// Vinyl (2026-11-11): your records (api/app/vinyl.py) - synced from your Discogs collection and wantlist, found on
// Discogs by name or the barcode on the back, or typed in - with grades, what you paid and what they're worth (Discogs,
// weekly), a listening log (scrobbled to Last.fm if you connect it), stats and an insurance export. Plays show on the
// calendar; records can be mentioned in the journal and wanted ones are on the wishlist.
export default {
  id: 'vinyl',
  name: 'Vinyl',
  // its colour (a warm record-label red: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx)
  hue: '#c0573e',
  banner: { scene: 'hills', seed: 33, time: 'blue', extras: ['moon', 'stars', 'lake'], tagline: 'Drop the needle.' },
  what: 'Records: your crate, what you play, what it is worth',
  Icon: VinylIcon,
  home: { Tiles: VinylTiles },
  actions: [
    { label: 'Add a record', Icon: VinylIcon, run: (app) => app.openPanel('addrecord', {}) },
  ],
  panels: { record: RecordPanel, addrecord: AddRecordPanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'crate', label: 'Crate', Icon: VinylIcon, render: () => <CrateView /> },
    { path: 'plays', label: 'Plays', Icon: ClockIcon, render: () => <PlaysView /> },
    { path: 'stats', label: 'Stats', Icon: GridIcon, render: () => <StatsView /> },
    { path: 'connect', label: 'Connect', Icon: GearIcon, render: () => <ConnectView /> },
  ],
}
