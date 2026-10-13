import { useNavigate } from 'react-router'
import { api, imageUrl, timeAgo } from '../api.js'
import { BoxIcon, CartIcon, JournalIcon, PlaneIcon } from '../components/icons.jsx'
import { MODULES } from '../modules/index.js'
import { useApp } from './app-context.js'
import JournalHome from './journal/JournalHome.jsx'
import { useNewPage } from './journal/JournalList.jsx'
import { useShared } from './useShared.js'

const greeting = (hour) => (hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening')

// A different line each day.
const TAGLINES = [
  'Track your hobbies. Plan your builds. Never waste a good paint again.',
  'Every kit in the stash is a promise. Keep one today.',
  'Progress, not perfection. One sprue at a time.',
  'Thin your paints. Thin them again.',
  'The best time to start a kit was yesterday. The second best is now.',
  "Time spent at the bench is never wasted.",
]
const tagline = () => TAGLINES[Math.floor(Date.now() / 86400000) % TAGLINES.length]

// How each kind of activity is coloured ("Finished" green, "Used" purple...).
const VERB_TONE = {
  Finished: 'ok', Bought: 'tint', Added: 'tint', Started: 'low', 'Worked on': 'low',
  Used: 'purple', Logged: 'teal', Wrote: 'teal', Removed: 'out',
}
const KIND = { model: 'Kit', supply: 'Supply', page: 'Journal' }

// Home: today at a glance.
//   hero            the date, a greeting and a line for the day, over a photo of what you've
//                   been working on, with "Write today's entry"
//   each module's stat tiles, then Recent activity beside Quick actions and the Journal,
//   then each module's own cards (Building now, Running low...)
export default function Home() {
  const { refreshKey } = useApp()
  const { data: activity } = useShared(`activity-${refreshKey}`, () => api.activity(8))
  const newPage = useNewPage()
  const now = new Date()
  const photo = activity?.find((a) => a.kind === 'model' && a.photo_updated) ?? activity?.find((a) => a.photo_updated)

  return (
    <section className="page home">
      <header className="hero" style={photo ? { '--hero-image': `url("${imageUrl(photo)}")` } : undefined}>
        <div className="hero-text">
          <p className="hero-date">{now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
          <h2>{greeting(now.getHours())}</h2>
          <p className="hero-tagline">{tagline()}</p>
          <button type="button" className="primary" onClick={() => newPage({
            title: now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' }),
          })}>Write today's entry</button>
        </div>
      </header>

      {MODULES.map((m) => <m.home.Stats key={m.id} />)}

      <div className="home-grid">
        <RecentActivity items={activity} />
        <div className="home-column">
          <QuickActions newPage={newPage} />
          <JournalHome />
        </div>
      </div>

      {MODULES.map((m) => <m.home.Cards key={m.id} />)}
    </section>
  )
}

function RecentActivity({ items }) {
  const { openItem, openModel } = useApp()
  const navigate = useNavigate()
  const open = (a) => (a.kind === 'model' ? openModel(a.ref) : a.kind === 'supply' ? (a.ref && openItem(a.ref))
    : navigate(`/journal/${a.ref}`))
  return (
    <section className="card home-card" aria-labelledby="home-activity">
      <h2 id="home-activity" className="home-card-title">Recent activity</h2>
      {!items ? <p className="muted small">Loading...</p> : items.length === 0
        ? <p className="muted small">Nothing yet. What you buy, build and write shows up here.</p> : (
          <ul className="list plain-list activity">
            {items.map((a) => (
              <li key={`${a.kind}-${a.ref}-${a.verb}-${a.at}`}>
                <button type="button" className="row-button" onClick={() => open(a)} disabled={a.kind === 'supply' && !a.ref}>
                  {a.photo_updated ? <img className="thumb" src={imageUrl(a)} alt="" loading="lazy" />
                    : <span className={`thumb thumb-icon ${VERB_TONE[a.verb]}`} aria-hidden="true">
                      {a.kind === 'page' ? <JournalIcon size={20} /> : a.kind === 'model' ? <PlaneIcon size={20} /> : <BoxIcon size={20} />}
                    </span>}
                  <span className="grow">
                    <span className="item-title">{a.title}</span>
                    <span className="item-meta">{timeAgo(a.at)} · {a.detail || KIND[a.kind]}</span>
                  </span>
                  <span className={`pill ${VERB_TONE[a.verb]}`}>{a.verb}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
    </section>
  )
}

function QuickActions({ newPage }) {
  const { openAdd, openModel } = useApp()
  const navigate = useNavigate()
  const actions = [
    { label: 'Add supply', Icon: BoxIcon, run: () => openAdd(null) },
    { label: 'New page', Icon: JournalIcon, run: () => newPage() },
    { label: 'Add kit', Icon: PlaneIcon, run: () => openModel(null) },
    { label: 'Shop Tamiya', Icon: CartIcon, run: () => navigate('/models/wishlist?shop=1') },
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
