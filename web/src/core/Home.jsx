import { useRef } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, timeAgo } from '../api.js'
import { BoxIcon, CalendarIcon, CartIcon, ChevronIcon, JournalIcon, PenIcon } from '../components/icons.jsx'
import { BannerArt, BannerPicture } from '../components/PageBanner.jsx'
import { CORE_AREAS } from './areas.js'
import { useBanners } from './banners.js'
import { MODULES } from '../modules/index.js'
import { KIND_ICON, KIND_NAME, VERB_TONE } from './activityKinds.js'
import { useApp } from './app-context.js'
import { ComingUp } from './calendar/CalendarPage.jsx'
import TodoHome from './todo/TodoHome.jsx'
import GoalNudges from './goals/GoalNudges.jsx'
import JournalHome from './journal/JournalHome.jsx'
import { useNewPage } from './journal/JournalList.jsx'
import { SiteCheckWarning, useFailingSites } from '../components/SiteChecks.jsx'
import { SystemWarning, useSystemAttention } from '../components/SystemStatus.jsx'
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

// Home's banner (drawn by App above the page, full width): the date, a greeting (with your name, if
// Settings has it) and a line for the day over your Home picture or a drawn landscape, with
// "Write today's entry".
export function HomeHero({ area }) {
  const { settings } = useApp()
  const banners = useBanners()
  const newPage = useNewPage()
  const now = new Date()
  const today = now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })
  return (
    <header className="hero page-banner home-banner" style={{ '--hue': area.hue }}>
      <div className="banner-art"><BannerArt area={area} photo={banners.home} /></div>
      <div className="hero-text">
        <p className="hero-date">{today}</p>
        <h2>{greeting(now.getHours())}{settings?.your_name && `, ${settings.your_name}`}</h2>
        <p className="hero-tagline">{tagline()}</p>
        <div className="hero-actions">
          <button type="button" className="primary hero-write" onClick={() => newPage({ title: today })}>
            Write today's entry <ChevronIcon size={16} />
          </button>
          <HomeAttention />
        </div>
      </div>
      <p className="hero-script" aria-hidden="true">Better things<br />outside of work.</p>
      <BannerPicture area={{ ...area, name: 'Home' }} photo={banners.home} />
    </header>
  )
}

// A "!" by "Write today's entry" when the app needs a look (a late backup, a lookup site that changed...); tap it
// for what and a link to Settings. Nothing when all is well. (It was a banner above the cards; user, 2026-10-26:
// a "!" keeps Home's layout still.)
function HomeAttention() {
  const system = useSystemAttention()
  const failing = useFailingSites()
  const ref = useRef(null)
  const count = (system?.attention.length ?? 0) + (failing.length ? 1 : 0)
  if (!count) return null
  const close = () => { if (ref.current) ref.current.open = false }
  return (
    <details className={`hero-attention${system?.worst === 'bad' ? ' bad' : ''}`} ref={ref}>
      <summary aria-label={`${count} thing${count === 1 ? '' : 's'} need${count === 1 ? 's' : ''} a look`}>!</summary>
      <div className="hero-attention-card">
        <SystemWarning data={system} onOpen={close} />
        <SiteCheckWarning failing={failing} onOpen={close} />
      </div>
    </details>
  )
}

// Home: today, like the front page of a magazine about your week.
//   (the banner above it: HomeHero)
//   a row of what matters now: a hobby's feature (your next trip), recent activity, your to-do list
//   Your hobbies: a card each, its picture and its numbers
//   Coming up (the calendar), Quick actions, the journal, Running low and each hobby's own cards
export default function Home() {
  const { refreshKey } = useApp()
  const { data: activity } = useShared(`activity-${refreshKey}`, () => api.activity(6))
  const newPage = useNewPage()
  const cards = MODULES.filter((m) => m.home?.Cards)
  const features = MODULES.filter((m) => m.home?.Feature)

  return (
    <section className="page home">
      <div className="home-now">
        {features.map((m) => <m.home.Feature key={m.id} />)}
        <RecentActivity items={activity} />
        <TodoHome />
      </div>
      <GoalNudges />

      <section className="home-hobbies" aria-labelledby="home-hobbies">
        <h2 id="home-hobbies" className="home-section-title">Your hobbies</h2>
        <Glance />
      </section>

      <div className="home-grid">
        <ComingUp />
        <JournalHome />
      </div>

      <QuickActions newPage={newPage} />

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
  { id: 'supplies', name: 'Supplies', Icon: BoxIcon, to: '/supplies', Tiles: SuppliesTiles, ...CORE_AREAS.supplies },
  ...MODULES.filter((m) => m.home?.Tiles).map((m) => ({ id: m.id, name: m.name, Icon: m.Icon, to: `/${m.id}/${m.pages[0].path}`,
    Tiles: m.home.Tiles, hue: m.hue, banner: m.banner })),
]

// Each card: a strip of the hobby's picture (yours, or its landscape) under its name, then its numbers.
function Glance() {
  const banners = useBanners()
  return (
    <div className="glance">
      {GLANCE.map((g) => (
        <div key={g.id} className="glance-card card" data-hobby={g.id} style={{ '--hue': g.hue }}>
          <Link to={g.to} className="glance-head">
            <span className="glance-art"><BannerArt area={g} photo={banners[g.id]} strip /></span>
            <g.Icon size={18} /><span>{g.name}</span><ChevronIcon size={14} />
          </Link>
          <div className="glance-tiles"><g.Tiles /></div>
        </div>
      ))}
    </div>
  )
}
