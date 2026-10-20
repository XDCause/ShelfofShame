import { Link, useNavigate } from 'react-router'
import { api, timeAgo } from '../api.js'
import { BoxIcon, CalendarIcon, CartIcon, ChevronIcon, JournalIcon, PenIcon } from '../components/icons.jsx'
import { MODULES } from '../modules/index.js'
import { KIND_ICON, KIND_NAME, VERB_TONE } from './activityKinds.js'
import { useApp } from './app-context.js'
import { ComingUp } from './calendar/CalendarPage.jsx'
import GoalsHome from './goals/GoalsHome.jsx'
import JournalHome from './journal/JournalHome.jsx'
import { useNewPage } from './journal/JournalList.jsx'
import { SiteCheckWarning } from '../components/SiteChecks.jsx'
import { RunningLow, SuppliesTiles } from './SuppliesHome.jsx'
import { useShared } from './useShared.js'

const greeting = (hour) => (hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening')

// A different line each day.
const TAGLINES = [
  'Your time, your hobbies. Make the most of being off the clock.',
  'Every kit in the stash is a promise. Keep one today.',
  'Progress, not perfection. One step at a time.',
  'A games night is never wasted.',
  'The best time to start was yesterday. The second best is now.',
  'Write it down: future you will want to know.',
]
const tagline = () => TAGLINES[Math.floor(Date.now() / 86400000) % TAGLINES.length]

// Home: today at a glance.
//   hero            the date, a greeting and a line for the day, over a photo of what you've
//                   been doing, with "Write today's entry"
//   stat tiles      supplies, then each hobby's (one shared row)
//   Recent activity beside Coming up (the calendar), Quick actions and the Journal
//   then Running low and each hobby's own cards (Building now...)
export default function Home() {
  const { refreshKey } = useApp()
  const { data: activity } = useShared(`activity-${refreshKey}`, () => api.activity(8))
  const newPage = useNewPage()
  const now = new Date()
  const photo = activity?.find((a) => a.photo_url && a.kind !== 'supply') ?? activity?.find((a) => a.photo_url)
  const cards = MODULES.filter((m) => m.home?.Cards)

  return (
    <section className="page home">
      <header className="hero" style={photo ? { '--hero-image': `url("${photo.photo_url}")` } : undefined}>
        <div className="hero-text">
          <p className="hero-date">{now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
          <h2>{greeting(now.getHours())}</h2>
          <p className="hero-tagline">{tagline()}</p>
          <button type="button" className="primary" onClick={() => newPage({
            title: now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' }),
          })}>Write today's entry</button>
        </div>
      </header>

      <SiteCheckWarning />
      <Glance />

      <div className="home-grid">
        <div className="home-column">
          <ComingUp />
          <RecentActivity items={activity} />
        </div>
        <div className="home-column">
          <QuickActions newPage={newPage} />
          <GoalsHome />
          <JournalHome />
        </div>
      </div>

      <div className="home-grid">
        <RunningLow />
        {cards.map((m) => <m.home.Cards key={m.id} />)}
      </div>
    </section>
  )
}

function RecentActivity({ items }) {
  const { openThing } = useApp()
  return (
    <section className="card home-card" aria-labelledby="home-activity">
      <h2 id="home-activity" className="home-card-title">Recent activity</h2>
      {!items ? <p className="muted small">Loading...</p> : items.length === 0
        ? <p className="muted small">Nothing yet. What you buy, build, play and write shows up here.</p> : (
          <ul className="list plain-list activity">
            {items.map((a) => {
              const Icon = KIND_ICON[a.kind] ?? BoxIcon
              return (
                <li key={`${a.kind}-${a.ref}-${a.verb}-${a.at}`}>
                  <button type="button" className="row-button" onClick={() => openThing(a.kind, a.ref)} disabled={!a.ref}>
                    {a.photo_url ? <img className="thumb" src={a.photo_url} alt="" loading="lazy" />
                      : <span className={`thumb thumb-icon ${VERB_TONE[a.verb]}`} aria-hidden="true"><Icon size={20} /></span>}
                    <span className="grow">
                      <span className="item-title">{a.title}</span>
                      <span className="item-meta">{timeAgo(a.at)} · {a.detail || KIND_NAME[a.kind]}</span>
                    </span>
                    <span className={`pill ${VERB_TONE[a.verb]}`}>{a.verb}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
    </section>
  )
}

// The core's quick actions, then each hobby's.
function QuickActions({ newPage }) {
  const app = useApp()
  const navigate = useNavigate()
  const actions = [
    { label: 'New page', Icon: JournalIcon, run: () => newPage() },
    { label: 'Whiteboard', Icon: PenIcon, run: () => newPage({ kind: 'whiteboard' }) },
    { label: 'Add event', Icon: CalendarIcon, run: () => app.openPanel('event', {}) },
    { label: 'Add supply', Icon: BoxIcon, run: () => app.openAdd(null) },
    { label: 'Wishlist', Icon: CartIcon, run: () => navigate('/wishlist?add=1') },
    ...MODULES.flatMap((m) => (m.actions ?? []).map((a) => ({ ...a, run: () => a.run({ ...app, navigate }) }))),
  ]
  return (
    <section className="card home-card" aria-labelledby="home-actions">
      <h2 id="home-actions" className="home-card-title">Quick actions</h2>
      <div className="quick-actions">
        {actions.map(({ label, Icon, run }) => (
          <button key={label} type="button" className="quick-action" onClick={run}>
            <Icon size={24} /><span>{label}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

// Each hobby's numbers in its own small card (name, icon, a link to it): a grid on a computer, a row
// you swipe through on a phone - so Home stays short. A hobby with nothing to show (not set up yet)
// leaves its card out.
const GLANCE = [
  { id: 'supplies', name: 'Supplies', Icon: BoxIcon, to: '/supplies', Tiles: SuppliesTiles },
  ...MODULES.filter((m) => m.home?.Tiles).map((m) => ({ id: m.id, name: m.name, Icon: m.Icon, to: `/${m.id}/${m.pages[0].path}`, Tiles: m.home.Tiles })),
]

function Glance() {
  return (
    <section className="glance" aria-label="Your hobbies at a glance">
      {GLANCE.map((g) => (
        <div key={g.id} className="glance-card card" data-hobby={g.id}>
          <Link to={g.to} className="glance-head">
            <g.Icon size={18} /><span>{g.name}</span><ChevronIcon size={14} />
          </Link>
          <div className="glance-tiles"><g.Tiles /></div>
        </div>
      ))}
    </section>
  )
}
