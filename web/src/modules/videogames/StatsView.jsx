import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { BarList, ColumnChart } from '../../components/charts.jsx'
import { useApp } from '../../core/app-context.js'
import { Change } from '../../core/Stat.jsx'
import { playtime, useSteamSummary } from './steam.jsx'
import { PlatformToggles, useCounting } from './OtherPlatforms.jsx'
import { AchievementList, PerfectCard } from './VideoGamesViews.jsx'

const monthName = (ym, long = false) => new Date(`${ym}-15T12:00:00`)
  .toLocaleDateString('en-AU', long ? { month: 'long', year: 'numeric' } : { month: 'short', year: '2-digit' })

// Your achievement hunting over time: a month's recap, a year of unlock days with your streaks,
// then charts (like SteamHunters' stats pages) - unlocks per month, how rare your achievements are,
// how far you are through the games you've started, and where the hours went.
export default function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const [counting] = useCounting()
  const { data: all } = useSteamSummary()          // shared with the dashboard: which platforms you have
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.videoGameStats(counting).then(setStats).catch((e) => setError(e.message)) }, [refreshKey, counting])
  if (error) return <p className="alert error">{error}</p>
  if (!stats) return <p className="muted loading">Loading...</p>

  const months = stats.by_month.map((m) => ({ label: monthName(m.month), value: m.count, tip: monthName(m.month, true) }))
  const total = stats.by_month.reduce((s, m) => s + m.count, 0)
  return (
    <section className="page stats">
      <PlatformToggles available={all?.available} />
      <div className="home-grid">
        <Recap counting={counting} />
        <UnlockCalendar days={stats.days} today={stats.today} streak={stats.streak} />
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

const addMonths = (ym, n) => {
  const [y, m] = ym.split('-').map(Number)
  const d = new Date(y, m - 1 + n, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}
const longDay = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'long' })

// One month at a time - or your lifetime: how many achievements (and the change from the month before), in how
// many games, the games you 100%'d, your best day, your rarest unlocks and where they came from.
function Recap({ counting }) {
  const { refreshKey, openPanel } = useApp()
  const [month, setMonth] = useState(null)
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.videoGameRecap(month, counting).then(setR).catch((e) => setError(e.message)) }, [month, refreshKey, counting])
  if (error) return <section className="card home-card wide-card"><p className="alert error">{error}</p></section>
  if (!r) return <section className="card home-card wide-card"><p className="muted loading">Loading...</p></section>
  const lifetime = r.month === 'all'
  const perfectCount = r.perfect_count ?? r.perfect.length
  return (
    <section className="card home-card wide-card recap" aria-label={lifetime ? 'Lifetime recap' : `${monthName(r.month, true)} recap`}>
      <div className="recap-head">
        {lifetime ? <h2 className="home-card-title">Lifetime</h2> : <>
          <button type="button" className="plain" onClick={() => setMonth(addMonths(r.month, -1))}
            disabled={!r.first || r.month <= r.first} aria-label="Month before">‹</button>
          <h2 className="home-card-title">{monthName(r.month, true)}</h2>
          <button type="button" className="plain" onClick={() => setMonth(addMonths(r.month, 1))}
            disabled={r.month >= r.this_month} aria-label="Month after">›</button>
        </>}
        <div className="segmented recap-span" role="group" aria-label="Recap of">
          <button type="button" aria-pressed={!lifetime} onClick={() => setMonth(null)}>Month</button>
          <button type="button" aria-pressed={lifetime} onClick={() => setMonth('all')}>Lifetime</button>
        </div>
      </div>
      {r.achievements === 0 ? <p className="muted">{lifetime ? 'No achievements unlocked yet.' : 'No achievements unlocked this month.'}</p> : (
        <>
          <div className="recap-numbers">
            <span><strong>{r.achievements.toLocaleString()}{!lifetime && <Change value={r.achievements - r.previous}
              what={r.month === r.this_month ? 'on the same days of the month before' : 'on the month before'} />}</strong>
              achievements</span>
            <span><strong>{r.games}</strong> game{r.games === 1 ? '' : 's'}</span>
            <span><strong>{perfectCount}</strong> at 100%</span>
            {r.best_day && <span><strong>{r.best_day.count}</strong> on your best day, {longDay(r.best_day.day)}</span>}
          </div>
          <div className="recap-grid">
            <div>
              <h3 className="section-title">Where they came from</h3>
              <BarList title="Game" valueLabel="Achievements" onPick={(row) => openPanel('videogame', { id: row.id })}
                rows={r.top_games.map((g) => ({ label: g.name, value: g.count, id: g.app_id }))} />
            </div>
            <div>
              <h3 className="section-title">Rarest unlocks</h3>
              <AchievementList items={r.rarest} />
            </div>
          </div>
          {r.perfect.length > 0 && (
            <>
              <h3 className="section-title">{!lifetime ? '100% this month' : perfectCount > r.perfect.length
                ? `Your latest ${r.perfect.length} at 100%` : 'Every game at 100%'}</h3>
              <div className="perfect-grid">{r.perfect.map((g) => <PerfectCard key={g.app_id} game={g} />)}</div>
            </>
          )}
        </>
      )}
    </section>
  )
}

// 53 weeks of days up to today, Monday first: [[{iso, n, first}]] (first = the first Monday of a month).
function calendarWeeks(today, counts) {
  const end = new Date(`${today}T12:00:00`)
  const d = new Date(end)
  d.setDate(d.getDate() - 52 * 7 - ((end.getDay() + 6) % 7))           // the Monday 52 weeks back
  const weeks = []
  while (d <= end) {
    if ((d.getDay() + 6) % 7 === 0) weeks.push([])
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    weeks[weeks.length - 1].push({ iso, n: counts.get(iso) ?? 0, first: d.getDate() <= 7 && (d.getDay() + 6) % 7 === 0 })
    d.setDate(d.getDate() + 1)
  }
  return weeks
}

// A year of unlock days, a square a day (weeks across, Monday at the top), darker = more unlocked
// that day, with your current and longest streaks. Levels are your own quartiles, so one huge day
// doesn't wash the rest out. Hover a day for its count; the table lists every day with an unlock.
// days = [{day, count}]; one / many name what's counted (Reading uses it for pages).
export function UnlockCalendar({ days, today, streak, title = 'Unlock calendar', one = 'achievement', many = 'achievements' }) {
  const [hover, setHover] = useState(null)
  const counts = new Map(days.map((d) => [d.day, d.count]))
  const sorted = days.map((d) => d.count).sort((a, b) => a - b)
  const q = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] ?? 1
  const cuts = [q(0.25), q(0.5), q(0.75)]
  const level = (n) => (!n ? 0 : n <= cuts[0] ? 1 : n <= cuts[1] ? 2 : n <= cuts[2] ? 3 : 4)

  const weeks = calendarWeeks(today, counts)
  const inYear = days.filter((d) => d.day >= weeks[0][0].iso)
  const total = inYear.reduce((s, d) => s + d.count, 0)
  return (
    <section className="card home-card wide-card">
      <h2 className="home-card-title">{title}</h2>
      <p className="muted small chart-sub">
        {total.toLocaleString()} {many} on {inYear.length} days in the last year
        {' · '}streak: <strong>{streak.current} day{streak.current === 1 ? '' : 's'}</strong>
        {' · '}longest: <strong>{streak.longest} days</strong>{streak.longest_end && ` (to ${longDay(streak.longest_end)})`}
      </p>
      <div className="heatmap-scroll" tabIndex={0} role="region" aria-label="Unlocks by day (scrolls sideways)">
        <div className="heatmap" role="img" aria-label={`${title}: ${total} ${many} on ${inYear.length} days in the last year`}>
          <div className="heatmap-months" aria-hidden="true">
            {weeks.map((w, i) => <span key={w[0].iso}>{w[0].first || i === 0 ? monthName(w[0].iso.slice(0, 7)).split(' ')[0] : ''}</span>)}
          </div>
          <div className="heatmap-grid">
            {weeks.map((w) => (
              <div key={w[0].iso} className="heatmap-week">
                {w.map((d) => (
                  <span key={d.iso} className={`heatmap-day l${level(d.n)}`}
                    onMouseEnter={() => setHover(d)} onMouseLeave={() => setHover(null)} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="heatmap-foot">
        <span className="muted small" aria-live="polite">
          {hover ? <><strong>{hover.n}</strong> {hover.n === 1 ? one : many} on {longDay(hover.iso)}</> : 'Hover a day to see its count'}
        </span>
        <span className="heatmap-key muted small" aria-hidden="true">Less{[0, 1, 2, 3, 4].map((l) => <span key={l} className={`heatmap-day l${l}`} />)}More</span>
      </div>
      <details className="chart-table">
        <summary>Show as a table</summary>
        <table>
          <thead><tr><th scope="col">Day</th><th scope="col">{many[0].toUpperCase() + many.slice(1)}</th></tr></thead>
          <tbody>{[...inYear].reverse().map((d) => <tr key={d.day}><td>{longDay(d.day)}</td><td>{d.count}</td></tr>)}</tbody>
        </table>
      </details>
    </section>
  )
}
