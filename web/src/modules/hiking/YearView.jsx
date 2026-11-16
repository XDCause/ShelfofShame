import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { ColumnChart } from '../../components/charts.jsx'
import { useApp } from '../../core/app-context.js'
import { hikeTime, km, metres } from './hikingParts.jsx'
import { plural } from './HomeTiles.jsx'
import YearMap from './YearMap.jsx'

// Your hiking year: distance, climb, hikes, the standouts and every track on one map (api/app/hiking.py /hiking/year).
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function YearView() {
  const { openPanel, refreshKey } = useApp()
  const [year, setYear] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.hikingYear(year).then(setData).catch((e) => setError(e.message)) }, [year, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const months = data.months.map((m, i) => ({ label: MONTHS[i], value: m.km, tip: `${plural(m.hikes, 'hike')}` }))
  const standout = (label, h, value) => h && (
    <div><dt>{label}</dt><dd><button type="button" className="plain" onClick={() => openPanel('hike', { id: h.hike_id })}>{h.name}</button>
      <span className="muted small"> {value} · {shortDate(h.hiked_on)}</span></dd></div>
  )
  return (
    <section className="page hiking">
      <div className="toolbar hike-year-bar">
        <select value={data.year} onChange={(e) => setYear(Number(e.target.value))} aria-label="Year">
          {(data.years.length ? data.years : [data.year]).map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>
      {data.hikes === 0 ? <p className="empty card">No hikes in {data.year}.</p> : (
        <>
          <section className="card">
            <h2 className="home-card-title">{data.year} in review</h2>
            <dl className="hike-year-facts">
              <div><dt>Hikes</dt><dd>{data.hikes} on {plural(data.days, 'day')}</dd></div>
              <div><dt>Distance</dt><dd>{km(data.km * 1000)}</dd></div>
              <div><dt>Climbed</dt><dd>{metres(data.ascent_m)}</dd></div>
              <div><dt>On the trail</dt><dd>{hikeTime(data.seconds)}</dd></div>
              {standout('Longest', data.longest, km(data.longest?.distance_m))}
              {standout('Highest', data.highest, metres(data.highest?.max_ele_m))}
              {standout('Biggest climb', data.biggest_climb, metres(data.biggest_climb?.ascent_m))}
              {data.best_month && <div><dt>Best month</dt><dd>{MONTHS[data.best_month.month - 1]}<span className="muted small"> {km(data.best_month.km * 1000)}</span></dd></div>}
              {data.most_hiked && <div><dt>Walked most</dt><dd>{data.most_hiked.name}<span className="muted small"> {data.most_hiked.times} times</span></dd></div>}
              {data.photos > 0 && <div><dt>Photos</dt><dd>{data.photos}</dd></div>}
            </dl>
          </section>
          <section className="card">
            <ColumnChart title="Kilometres each month" rows={months} valueLabel="km" />
          </section>
          <section className="card">
            <h2 className="home-card-title">Every track</h2>
            {data.tracks.length ? <YearMap tracks={data.tracks} label={`Map of every track in ${data.year}`} />
              : <p className="muted small">None of this year's hikes has a GPS track.</p>}
            <p className="muted small">Paths you walked more than once show darker.</p>
          </section>
        </>
      )}
    </section>
  )
}
