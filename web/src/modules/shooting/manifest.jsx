import { CrosshairIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { GearView } from '../volleyball/VolleyballViews.jsx'
import { startShooting } from './ShootingLive.jsx'
import { AmmoPanel, RangePanel, RiflePanel, SessionPanel } from './ShootingPanels.jsx'
import { AmmoView, Dashboard, DopeView, RiflesView, SessionsView, ShootingTiles } from './ShootingViews.jsx'

// Precision shooting (api/app/shooting.py, shooting_sessions.py, shotmath.py): smallbore / rimfire and long-range
// rifle with factory ammo. Rifles and scopes (round count, cleaning due, Queensland Permit to Acquire), ammunition
// (what's left as sessions use it), ranges and the club-shoot count, sessions with every group (MOA / MIL,
// chronograph SD / ES, what to dial), your DOPE card, and gear on the shared gear pages (gear.hobby = 'shooting').
// underConstruction keeps it in dev only until you say it's done (modules/index.js).
export default {
  id: 'shooting',
  name: 'Precision shooting',
  what: 'Rifles, ammo, range sessions, groups and your DOPE',
  Icon: CrosshairIcon,
  underConstruction: true,
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
