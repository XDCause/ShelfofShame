import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { BarList, LineChart } from '../../components/charts.jsx'
import { GolfIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { GOLF_STEPS, GolfSettingsCard, HandicapLine, Numbers, PlaysLike, StrokesGained } from './golfCards.jsx'
import { KIND_LABELS, hcpText, num, oneADay, pct, plural, toPar } from './golfFormat.js'
import { useGolfCourses, useGolfSettings } from './golfParts.jsx'

// Golf's stats: your last 5 / 10 / 20 / every round (at one course, or all): scoring, driving, greens, putting, the
// short game, par 3s / 4s / 5s, front and back nines, score kinds, "plays like", strokes gained - then the handicap
// (the last 20 differentials, which count, its line, what to shoot next) and the settings.
const LASTS = [[5, 'Last 5'], [10, 'Last 10'], [20, 'Last 20'], [1000, 'All']]
const half = (v) => (v == null ? '—' : `${toPar(Math.round(v * 10) / 10)} a nine`)

export function StatsView() {
  const { refreshKey, openPanel } = useApp()
  const courses = useGolfCourses()
  const settings = useGolfSettings()
  const [last, setLast] = useState(20)
  const [course, setCourse] = useState('')
  const [st, setSt] = useState(null)
  const [hcp, setHcp] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.golfStats({ last, course_id: course }).then(setSt).catch((e) => setError(e.message))
  }, [last, course, refreshKey])
  useEffect(() => { api.golfHandicap().then(setHcp).catch(() => setHcp(null)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!st) return <p className="muted loading">Loading...</p>
  const scores = oneADay(st.trend.filter((t) => t.gross != null).map((t) => ({ x: t.day, y: t.gross, tip: `${t.course} · ${toPar(t.to_par)}` })))
  const points = oneADay(st.trend.filter((t) => t.points != null && !t.nine).map((t) => ({ x: t.day, y: t.points, tip: t.course })))
  const kinds = Object.entries(KIND_LABELS).map(([k, label]) => ({ label, value: st.kinds?.[k] ?? 0 }))
  return (
    <section className="page golf">
      <div className="toolbar">
        <div className="chip-row" role="group" aria-label="Rounds">
          {LASTS.map(([n, label]) => (
            <button key={n} type="button" className="chip-filter" aria-pressed={last === n} onClick={() => setLast(n)}>{label}</button>
          ))}
        </div>
        <select value={course} onChange={(e) => setCourse(e.target.value)} aria-label="Course">
          <option value="">Every course</option>
          {(courses ?? []).map((c) => <option key={c.course_id} value={c.course_id}>{c.name}</option>)}
        </select>
      </div>
      {st.rounds === 0 ? (
        course ? <p className="empty card">No finished rounds at that course yet.</p> : (
          <EmptyState Icon={GolfIcon} title="No finished rounds yet" action="Start a round" onAction={() => openPanel('golfnewround', {})}>
            Play a round on the phone or type in a card: your stats, where you lose strokes and your handicap show here.</EmptyState>
        )
      ) : (
        <div className="home-grid">
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Scoring</h2>
              <Numbers items={[
                { label: 'Rounds', value: st.rounds, sub: `${st.holes} holes` },
                { label: 'Average (18)', value: st.average ?? '—' },
                { label: 'Best (18)', value: st.best ?? '—' },
                st.average_points != null && { label: 'Stableford average', value: st.average_points, sub: `best ${st.best_points}` },
                { label: 'Par 3s', value: num(st.par3, 2) },
                { label: 'Par 4s', value: num(st.par4, 2) },
                { label: 'Par 5s', value: num(st.par5, 2) },
                { label: 'Front nine', value: half(st.front_vs_par) },
                { label: 'Back nine', value: half(st.back_vs_par) },
              ]} />
              {scores.length > 1 && <LineChart title="Gross score (18 holes)" rows={scores} valueLabel="strokes" height={160} stepChoices={GOLF_STEPS} />}
              {points.length > 1 && (
                <>
                  <h3 className="golf-subhead">Stableford points</h3>
                  <LineChart title="Stableford points" rows={points} valueLabel="points" height={140} stepChoices={GOLF_STEPS} />
                </>
              )}
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Tee to green</h2>
              <Numbers items={[
                { label: 'Fairways hit', value: pct(st.fairways), sub: st.fairways != null ? `${pct(st.missed_left)} left · ${pct(st.missed_right)} right` : null },
                { label: 'Greens in regulation', value: pct(st.gir) },
                { label: 'Putts a round', value: num(st.putts) },
                { label: 'Putts per green hit', value: num(st.putts_per_gir, 2) },
                { label: 'Three-putts a round', value: num(st.three_putts) },
                { label: 'Scrambling', value: pct(st.scrambling), sub: 'par or better after missing the green' },
                { label: 'Sand saves', value: pct(st.sand_saves) },
                { label: 'Penalties a round', value: num(st.penalties) },
              ]} />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Score kinds</h2>
              <BarList title="Holes by score" rows={kinds} valueLabel="holes" />
            </section>
          </div>
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Plays like</h2>
              <PlaysLike stats={st} bench={st.bench} target={st.target} />
            </section>
            <section className="card home-card">
              <h2 className="home-card-title">Strokes gained</h2>
              <StrokesGained sg={st.sg} />
            </section>
          </div>
        </div>
      )}
      <div className="home-grid">
        <section className="card home-card">
          <h2 className="home-card-title">Handicap</h2>
          {hcp ? <HandicapCard h={hcp} /> : <p className="muted small">Loading...</p>}
        </section>
        <section className="card home-card" id="golf-settings">
          <h2 className="home-card-title">Your handicap settings</h2>
          {settings && courses ? <GolfSettingsCard key={JSON.stringify(settings)} settings={settings} courses={courses} />
            : <p className="muted small">Loading...</p>}
        </section>
      </div>
    </section>
  )
}

// The estimate and the official one, the line, the last 20 differentials (the ones that count marked) and what
// you'd need next time to bring it down.
function HandicapCard({ h }) {
  const { openPanel } = useApp()
  return (
    <>
      <Numbers items={[
        { label: 'Estimate', value: hcpText(h.estimate), sub: h.estimate != null ? `best ${h.best} of ${h.of}` : `${h.counting} of 3 rounds` },
        h.official != null && { label: 'Official (GolfLink)', value: hcpText(h.official), sub: h.official_as_of ? `as of ${shortDate(h.official_as_of)}` : null },
        h.target != null && { label: 'Target', value: hcpText(h.target) },
      ]} />
      <HandicapLine history={h.history} />
      {h.need && (
        <p className="golf-need">To bring it down next round: a differential under <strong>{num(h.need.differential)}</strong>
          {h.need.gross != null && <> - about <strong>{h.need.gross}</strong> or better (adjusted gross) at {h.need.course}, {h.need.tees} tees</>}.</p>
      )}
      {h.rounds.length === 0 ? (
        <p className="muted small">A round counts once it's finished, from tees with a rating and slope (Course &gt; Tees), and isn't a team
          format. Three of them make your first estimate.</p>
      ) : (
        <>
          <h3 className="golf-subhead">Your last {plural(h.rounds.length, 'differential')}</h3>
          <div className="golf-table-wrap" tabIndex={0} role="region" aria-label="Differentials (scrolls sideways)">
            <table className="golf-table">
              <thead><tr><th scope="col">Date</th><th scope="col">Course</th><th scope="col">Score</th><th scope="col">Diff.</th><th scope="col">Counts</th></tr></thead>
              <tbody>
                {h.rounds.map((r) => (
                  <tr key={r.round_id} className={r.counted ? 'golf-counted' : undefined}>
                    <td><button type="button" className="link-plain golf-cell-button" onClick={() => openPanel('golfround', { id: r.round_id })}>
                      {shortDate(r.played_on)}</button></td>
                    <td>{r.course_name}{r.of === 9 && <span className="muted small"> (9)</span>}</td>
                    <td>{r.gross ?? `${r.points} pts`}</td>
                    <td>{num(r.differential)}</td>
                    <td>{r.counted ? <span className="pill ok">Counts</span> : <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
