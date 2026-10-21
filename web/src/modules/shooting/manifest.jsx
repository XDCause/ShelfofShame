import { CrosshairIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { ShootingTiles } from './HomeTiles.jsx'
import { part } from '../lazy.js'

// its pages and panels: loaded when first shown (modules/lazy.js)
const GearView = part(() => import('../volleyball/VolleyballViews.jsx'), 'GearView')
const startShooting = (app) => import('./ShootingLive.jsx').then((m) => m.startShooting(app))
const AmmoPanel = part(() => import('./ShootingPanels.jsx'), 'AmmoPanel')
const RangePanel = part(() => import('./ShootingPanels.jsx'), 'RangePanel')
const RiflePanel = part(() => import('./ShootingPanels.jsx'), 'RiflePanel')
const SessionPanel = part(() => import('./ShootingPanels.jsx'), 'SessionPanel')
const AmmoView = part(() => import('./ShootingViews.jsx'), 'AmmoView')
const Dashboard = part(() => import('./ShootingViews.jsx'), 'Dashboard')
const DopeView = part(() => import('./ShootingViews.jsx'), 'DopeView')
const RiflesView = part(() => import('./ShootingViews.jsx'), 'RiflesView')
const SessionsView = part(() => import('./ShootingViews.jsx'), 'SessionsView')

// Precision shooting (api/app/shooting.py, shooting_sessions.py, shotmath.py): smallbore / rimfire and long-range
// rifle with factory ammo. Rifles and scopes (round count, cleaning due, Queensland Permit to Acquire), ammunition
// (what's left as sessions use it), ranges and the club-shoot count, sessions with every group (MOA / MIL,
// chronograph SD / ES, what to dial), your DOPE card, and gear on the shared gear pages (gear.hobby = 'shooting').
export default {
  id: 'shooting',
  name: 'Precision shooting',
  // its colour (olive: sidebar icon, Home card, banner) and its banner (components/Landscape.jsx scenes)
  hue: '#9aa33f',
  banner: { scene: 'mesa', seed: 31, extras: ['birds', 'clouds'], tagline: 'Slow is smooth. Smooth is accurate.' },
  what: 'Rifles, ammo, range sessions, groups and your DOPE',
  Icon: CrosshairIcon,
  home: { Tiles: ShootingTiles },
  actions: [{ label: 'Start shooting', Icon: CrosshairIcon, run: (app) => startShooting(app).catch((e) => app.showToast(e.message)) }],
  panels: { shootsession: SessionPanel, rifle: RiflePanel, ammo: AmmoPanel, shootrange: RangePanel },
  pages: [
    { path: 'dashboard', label: 'Dashboard', Icon: TrophyIcon, render: () => <Dashboard /> },
    { path: 'sessions', label: 'Sessions', Icon: CrosshairIcon, render: () => <SessionsView /> },
    { path: 'rifles', label: 'Rifles', Icon: CrosshairIcon, render: () => <RiflesView /> },
    { path: 'ammo', label: 'Ammo', Icon: TargetIcon, render: () => <AmmoView /> },
    { path: 'dope', label: 'DOPE', Icon: TargetIcon, render: () => <DopeView /> },
    { path: 'gear', label: 'Gear', Icon: CrosshairIcon, render: () => <GearView hobby="shooting" Icon={CrosshairIcon} /> },
  ],
}
