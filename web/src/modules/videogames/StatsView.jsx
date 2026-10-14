import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { BarList, ColumnChart } from '../../components/charts.jsx'
import { useApp } from '../../core/app-context.js'
import { playtime } from './steam.jsx'

const monthName = (ym, long = false) => new Date(`${ym}-15T12:00:00`)
  .toLocaleDateString('en-AU', long ? { month: 'long', year: 'numeric' } : { month: 'short', year: '2-digit' })

// Charts about your achievement hunting (like SteamHunters' stats pages): unlocks over time, how
// rare your achievements are, how far you are through the games you've started, and where the
// hours went.
export default function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.videoGameStats().then(setStats).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!stats) return <p className="muted loading">Loading...</p>

  const months = stats.by_month.map((m) => ({ label: monthName(m.month), value: m.count, tip: monthName(m.month, true) }))
  const total = stats.by_month.reduce((s, m) => s + m.count, 0)
  return (
    <section className="page stats">
      <div className="home-grid">
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Achievements unlocked per month</h2>
          <p className="muted small chart-sub">{total.toLocaleString()} in the last {months.length} months</p>
          <ColumnChart title="Month" rows={months} valueLabel="achievements" tickEvery={3} />
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">How rare your achievements are</h2>
          <p className="muted small chart-sub">By the share of all players who have each one</p>
          <ColumnChart title="Players who have it" valueLabel="achievements" labelValues
            rows={stats.rarity.map((b) => ({ label: b.label, value: b.count }))} />
        </section>
        <section className="card home-card">
          <h2 className="home-card-title">Started games by completion</h2>
          <p className="muted small chart-sub">How much of each game you've unlocked</p>
          <ColumnChart title="Completion" valueLabel="games" labelValues
            rows={stats.completion.map((b) => ({ label: b.label, value: b.count }))} />
        </section>
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Most played</h2>
          <BarList title="Game" valueLabel="Played"
            rows={stats.most_played.map((g) => ({ label: g.name, value: g.playtime_minutes, text: playtime(g.playtime_minutes), id: g.app_id }))}
            onPick={(r) => openPanel('videogame', { id: r.id })} />
        </section>
      </div>
    </section>
  )
}
