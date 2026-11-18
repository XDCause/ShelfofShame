import { DiveIcon, DropsIcon, GlobeIcon, ListIcon, PulseIcon, ShieldIcon, SuitcaseIcon, TargetIcon, TrophyIcon, WrenchIcon } from '../../components/icons.jsx'
import { ScubaTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const Dashboard = part(() => import('./ScubaViews.jsx'), 'Dashboard')
const LogView = part(() => import('./ScubaViews.jsx'), 'LogView')
const PlanView = part(() => import('./ScubaPlan.jsx'), 'PlanView')
const ConditionsView = part(() => import('./ScubaConditions.jsx'), 'ConditionsView')
const SitesView = part(() => import('./ScubaSites.jsx'), 'SitesView')
const TripsView = part(() => import('./ScubaTrips.jsx'), 'TripsView')
const SpeciesView = part(() => import('./ScubaStats.jsx'), 'SpeciesView')
const StatsView = part(() => import('./ScubaStats.jsx'), 'StatsView')
const GearView = part(() => import('./ScubaGear.jsx'), 'GearView')
const CertsView = part(() => import('./ScubaGear.jsx'), 'CertsView')
const DivePanel = part(() => import('./ScubaPanels.jsx'), 'DivePanel')
const NewDivePanel = part(() => import('./ScubaPanels.jsx'), 'NewDivePanel')
const SitePanel = part(() => import('./ScubaSites.jsx'), 'SitePanel')
const TripPanel = part(() => import('./ScubaTrips.jsx'), 'TripPanel')
const CertPanel = part(() => import('./ScubaGear.jsx'), 'CertPanel')
const ServicePanel = part(() => import('./ScubaGear.jsx'), 'ServicePanel')
const ImportPanel = part(() => import('./ScubaImport.jsx'), 'ImportPanel')

// Scuba diving (2026-11-18, from a look at Subsurface, MacDive, Shearwater Cloud, Garmin Dive, Diving Log and Dive Kit):
// a numbered logbook that carries on from your paper one, dives imported from a dive computer's UDDF / Subsurface file
// with their depth profile (ascent rate, safety stop, tissue loading), a planner and nitrox calculators, sites (by hand or
// from OpenStreetMap) with a marine forecast and a dive-day verdict, trips, a life list, stats, gear with service
// reminders, certification cards and the no-fly time after your last dive.
// api/app/scuba.py, scuba_dives.py, scuba_stats.py, scuba_tools.py, divemath.py, diveimport.py.
export default {
  id: 'scuba',
  name: 'Scuba diving',
  // its colour (reef blue: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx: the coast scene is the sea)
  hue: '#1f8fb3',
  banner: { scene: 'coast', seed: 27, time: 'blue', extras: ['clouds'], tagline: 'Down where it is quiet.' },
  what: 'A dive logbook with profiles, sites, a planner, conditions and gear service',
  Icon: DiveIcon,
  home: { Tiles: ScubaTiles },
  actions: [{ label: 'Log a dive', Icon: DiveIcon, run: (app) => app.openPanel('scubanewdive', {}) }],
  panels: { scubadive: DivePanel, scubanewdive: NewDivePanel, scubasite: SitePanel, scubatrip: TripPanel, scubacert: CertPanel,
            scubaservice: ServicePanel, scubaimport: ImportPanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'log', label: 'Logbook', Icon: ListIcon, render: () => <LogView /> },
    { path: 'plan', label: 'Plan', Icon: PulseIcon, render: () => <PlanView /> },
    { path: 'conditions', label: 'Conditions', Icon: DropsIcon, render: () => <ConditionsView /> },
    { path: 'sites', label: 'Sites', Icon: TargetIcon, render: () => <SitesView /> },
    { path: 'trips', label: 'Trips', Icon: SuitcaseIcon, render: () => <TripsView /> },
    { path: 'species', label: 'Life list', Icon: GlobeIcon, render: () => <SpeciesView /> },
    { path: 'stats', label: 'Stats', Icon: TrophyIcon, render: () => <StatsView /> },
    { path: 'gear', label: 'Gear', Icon: WrenchIcon, render: () => <GearView /> },
    { path: 'certs', label: 'Certs', Icon: ShieldIcon, render: () => <CertsView /> },
  ],
}
