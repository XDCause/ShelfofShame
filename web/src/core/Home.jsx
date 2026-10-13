import { MODULES } from '../modules/index.js'
import JournalHome from './journal/JournalHome.jsx'

const greeting = (hour) => (hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening')

// Home: today at a glance. The journal first, then each hobby module's own card (manifest
// HomeCard). The calendar will join it (docs/ROADMAP.md).
export default function Home() {
  const now = new Date()
  return (
    <section className="page home">
      <header className="home-head">
        <p className="muted">{now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
        <h2>{greeting(now.getHours())}</h2>
      </header>
      <JournalHome />
      {MODULES.map((m) => <m.HomeCard key={m.id} />)}
    </section>
  )
}
