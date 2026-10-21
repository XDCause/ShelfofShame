import { useEffect, useState } from 'react'
import { api, dayDate, isoDay, shortDate } from '../../api.js'
import { useApp } from '../app-context.js'
import { reviewPage } from './blocks.js'
import { useNewPage } from './JournalList.jsx'
import { MOODS } from './moods.js'

const RANGES = [[30, '30 days'], [90, '3 months'], [365, 'A year']]
const FACE = (avg) => MOODS[Math.min(4, Math.max(0, Math.round(5 - avg)))]       // 5 great ... 1 rough
const weekday = (iso) => dayDate(iso).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'short' })

// Journal > Insights: how you've felt and what goes with your good days - your hobbies, from their own logs (no other
// journal app knows when you played volleyball). Plus the weekly / monthly review pages.
export default function JournalInsights() {
  const { refreshKey, showToast } = useApp()
  const newPage = useNewPage()
  const [days, setDays] = useState(90)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.journalInsights(days).then(setData).catch((e) => setError(e.message)) }, [days, refreshKey])

  const review = async (span) => {
    const end = new Date()
    const start = new Date()
    start.setDate(end.getDate() - (span - 1))
    try {
      const r = await api.journalReview(isoDay(start), isoDay(end))
      newPage({ title: `Review: ${span > 7 ? 'month' : 'week'} to ${shortDate(isoDay(end))}`, tags: ['review'], content: reviewPage(r, weekday) })
    } catch (e) {
      showToast(`Couldn't make the review: ${e.message}`)
    }
  }

  return (
    <section className="page">
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="How far back">
          {RANGES.map(([d, label]) => <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}>{label}</button>)}
        </div>
        <span className="grow" />
        <button type="button" className="secondary" onClick={() => review(30)}>Monthly review</button>
        <button type="button" className="primary" onClick={() => review(7)}>Write my weekly review</button>
      </div>
      {error && <p className="alert error">{error}</p>}
      {data && (
        <>
          <div className="jin-stats">
            <Stat value={data.pages} label="pages written" />
            <Stat value={data.writing_days} label={`of ${days} days written on`} />
            <Stat value={data.mood_days} label="days with a mood" />
            <Stat value={data.usual != null ? `${FACE(data.usual).face} ${FACE(data.usual).label}` : '–'} label="your usual mood" />
          </div>
          {data.mood_days === 0 ? (
            <p className="empty card">No moods yet in this time. Pick a face at the top of a page and your insights will grow here.</p>
          ) : (
            <div className="jin-grid">
              <section className="card">
                <h2 className="jin-title">Mood, week by week</h2>
                <MoodLine weekly={data.weekly} />
                <Spread spread={data.spread} total={data.mood_days} />
              </section>
              <section className="card">
                <h2 className="jin-title">Your hobbies and your mood</h2>
                {data.by_hobby.length === 0 ? (
                  <p className="muted small">After 3 days with a mood on which you did a hobby (from its own log), it shows here: whether
                    those days feel better or worse than usual.</p>
                ) : (
                  <ul className="jin-hobbies">
                    {data.by_hobby.map((h) => (
                      <li key={h.hobby}>
                        <span className="jin-hobby-name">{h.hobby}<span className="muted small"> · {h.days} days</span></span>
                        <span className={`jin-bar ${h.vs_usual >= 0 ? 'up' : 'down'}`}
                          style={{ '--size': `${Math.min(100, Math.abs(h.vs_usual) * 40)}%` }} aria-hidden="true"><i /></span>
                        <span className="jin-hobby-what">{FACE(h.average).face} {h.vs_usual > 0.05 ? `better than usual (+${h.vs_usual})`
                          : h.vs_usual < -0.05 ? `harder than usual (${h.vs_usual})` : 'about usual'}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {data.words.length > 0 && (
                  <>
                    <h3 className="section-title">Words you use most</h3>
                    <div className="chips">{data.words.map((w) => <span key={w.word} className="chip">{w.word} <span className="chip-count">{w.n}</span></span>)}</div>
                  </>
                )}
              </section>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Stat({ value, label }) {
  return <div className="card jin-stat"><strong>{value}</strong><span className="muted small">{label}</span></div>
}

// The weekly average (1 rough - 5 great) as a line; each week's point says its number (hover, or the table).
function MoodLine({ weekly }) {
  const W = 560
  const H = 170
  const pad = { l: 34, r: 12, t: 12, b: 26 }
  if (weekly.length === 0) return null
  const x = (i) => pad.l + (weekly.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (weekly.length - 1))
  const y = (v) => pad.t + ((5 - v) * (H - pad.t - pad.b)) / 4
  const line = weekly.map((w, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(w.average).toFixed(1)}`).join(' ')
  const tick = (w) => dayDate(w.week).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })
  return (
    <figure className="jin-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Average mood each week">
        {[5, 4, 3, 2, 1].map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} className="jin-grid-line" />
            <text x={pad.l - 8} y={y(v) + 5} textAnchor="end" className="jin-axis">{MOODS[5 - v].face}</text>
          </g>
        ))}
        <path d={line} className="jin-line" />
        {weekly.map((w, i) => (
          <circle key={w.week} cx={x(i)} cy={y(w.average)} r="5" className="jin-dot">
            <title>{`Week of ${tick(w)}: ${w.average} (${w.days} day${w.days === 1 ? '' : 's'})`}</title>
          </circle>
        ))}
        {weekly.map((w, i) => (i === 0 || i === weekly.length - 1 || weekly.length < 7) && (
          <text key={`t${w.week}`} x={x(i)} y={H - 6} className="jin-axis"
            textAnchor={weekly.length === 1 ? 'middle' : i === 0 ? 'start' : i === weekly.length - 1 ? 'end' : 'middle'}>{tick(w)}</text>
        ))}
      </svg>
      <details className="jin-table">
        <summary className="small">Show as a table</summary>
        <table className="table compact">
          <thead><tr><th>Week of</th><th>Average</th><th>Days</th></tr></thead>
          <tbody>{weekly.map((w) => <tr key={w.week}><td>{tick(w)}</td><td>{FACE(w.average).face} {w.average}</td><td>{w.days}</td></tr>)}</tbody>
        </table>
      </details>
    </figure>
  )
}

// How the days split between the five moods.
function Spread({ spread, total }) {
  return (
    <div className="jin-spread">
      <div className="jin-spread-bar" aria-hidden="true">
        {MOODS.filter((m) => spread[m.id]).map((m) => <span key={m.id} className={m.tone} style={{ flexGrow: spread[m.id] }} />)}
      </div>
      <ul className="jin-spread-key">
        {MOODS.map((m) => <li key={m.id}>{m.face} {m.label} <strong>{spread[m.id] ?? 0}</strong><span className="muted"> ({Math.round(((spread[m.id] ?? 0) / total) * 100)}%)</span></li>)}
      </ul>
    </div>
  )
}
