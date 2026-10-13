import { MODULES } from '../modules/index.js'

const greeting = (hour) => (hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening')

// Home: today at a glance. Each hobby module adds its own card (manifest HomeCard). The journal
// and calendar will join it (docs/ROADMAP.md).
export default function Home() {
  const now = new Date()
  return (
    <section className="page home">
      <header className="home-head">
        <p className="muted">{now.toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
        <h2>{greeting(now.getHours())}</h2>
      </header>
      {MODULES.map((m) => <m.HomeCard key={m.id} />)}
    </section>
  )
}
