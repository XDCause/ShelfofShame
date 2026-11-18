import { FishIcon, GlobeIcon, ListIcon, PulseIcon, RodIcon, TargetIcon, TrophyIcon, WrenchIcon } from '../../components/icons.jsx'
import { FishingTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const Dashboard = part(() => import('./FishingViews.jsx'), 'Dashboard')
const TripsView = part(() => import('./FishingViews.jsx'), 'TripsView')
const LiveView = part(() => import('./FishingLive.jsx'), 'LiveView')
const ForecastView = part(() => import('./FishingForecast.jsx'), 'ForecastView')
const SpotsView = part(() => import('./FishingSpots.jsx'), 'SpotsView')
const SpeciesView = part(() => import('./FishingSpecies.jsx'), 'SpeciesView')
const TackleView = part(() => import('./FishingTackle.jsx'), 'TackleView')
const StatsView = part(() => import('./FishingStats.jsx'), 'StatsView')
const TripPanel = part(() => import('./FishingPanels.jsx'), 'TripPanel')
const NewTripPanel = part(() => import('./FishingPanels.jsx'), 'NewTripPanel')
const CatchPanel = part(() => import('./FishingPanels.jsx'), 'CatchPanel')
const SpotPanel = part(() => import('./FishingSpots.jsx'), 'SpotPanel')
const SpeciesPanel = part(() => import('./FishingSpecies.jsx'), 'SpeciesPanel')
const LurePanel = part(() => import('./FishingTackle.jsx'), 'LurePanel')

// Fishing (2026-11-18, from a look at Fishbrain, FishAngler, Fishing Points, Anglr, Fishidy, iAngler and Qld Fishing 2.0):
// a trip log with its catches (species, length, kept / released, lure, photos) and the conditions saved with each trip,
// logged on the water from the phone (works without signal), a fishing forecast per spot (solunar, tide, wind,
// pressure), spots (by hand or boat ramps from OpenStreetMap), the tackle box, the rules YOU type per species (the app
// ships none: they change, and a wrong number could be a fine) with a warning when a kept fish breaks them, and what
// works for you (stats by month, tide, moon, hour, lure, spot).
// api/app/fishing.py (+ fishing_catches.py, fishing_stats.py), fishing_tools.py, solunar.py.
export default {
  id: 'fishing',
  name: 'Fishing',
  // its colour (a river green: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx: the coast
  // scene is the water; a dawn sky, no clouds or trees)
  hue: '#2f7d5b',
  banner: { scene: 'coast', seed: 41, time: 'dawn', extras: ['clouds'], tagline: 'One more cast.' },
  what: 'A fishing log with catches, spots, a forecast, the tackle box and what works for you',
  Icon: FishIcon,
  home: { Tiles: FishingTiles },
  actions: [{ label: 'Log a catch', Icon: FishIcon, run: (app) => app.navigate('/fishing/live') }],
  panels: { fishingtrip: TripPanel, fishingnewtrip: NewTripPanel, fishingcatch: CatchPanel, fishingspot: SpotPanel,
            fishingspecies: SpeciesPanel, fishinglure: LurePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'live', label: 'On the water', Icon: FishIcon, render: () => <LiveView /> },
    { path: 'trips', label: 'Trips', Icon: ListIcon, render: () => <TripsView /> },
    { path: 'forecast', label: 'Forecast', Icon: PulseIcon, render: () => <ForecastView /> },
    { path: 'spots', label: 'Spots', Icon: TargetIcon, render: () => <SpotsView /> },
    { path: 'species', label: 'Species', Icon: GlobeIcon, render: () => <SpeciesView /> },
    { path: 'tackle', label: 'Tackle', Icon: RodIcon, render: () => <TackleView /> },
    { path: 'stats', label: 'Stats', Icon: WrenchIcon, render: () => <StatsView /> },
  ],
}
