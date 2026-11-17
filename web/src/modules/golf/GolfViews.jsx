import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, shortDate } from '../../api.js'
import { GolfIcon, TargetIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import Stat from '../../core/Stat.jsx'
import { LineChart } from '../../components/charts.jsx'
import { GOLF_STEPS, HandicapLine, PlaysLike, RoundRow } from './golfCards.jsx'
import { hcpText, oneADay, plural, toPar } from './golfFormat.js'
import { useGolfCourses, useGolfSettings, useGolfSummary } from './golfParts.jsx'

// Golf's dashboard (the handicap, a round in play, the last rounds, "plays like", best rounds, the scoring trend)
// and the list of every round.

export function Dashboard() {
  const { data: s, error } = useGolfSummary()
  const settings = useGolfSettings()
  const { openPanel, changed, showToast } = useApp()
  const navigate = useNavigate()
  const [home, setHome] = useState(null)
  const homeId = settings?.home_course_id
  useEffect(() => {
    if (homeId) api.golfCourse(homeId).then(setHome).catch(() => setHome(null))
  }, [homeId, s])
  if (error) return <p className="alert error">{error}</p>
  if (!s) return <p className="muted loading">Loading...</p>
  const h = s.handicap
  const homeTee = homeId && home?.course_id === homeId ? home.tees.find((t) => t.daily_handicap != null) : null
  const fillBag = async () => {
    try {
      await api.golfStandardBag()
      changed()
      showToast('A standard bag is in: edit the carries to yours.')
      navigate('/golf/bag')
    } catch (e) {
      showToast(e.message)
    }
  }
  const scores = oneADay(s.trend.filter((t) => t.gross != null).map((t) => ({ x: t.day, y: t.gross, tip: `${t.course} · ${toPar(t.to_par)}` })))
  const fresh = s.rounds === 0 && s.playing.length === 0
  return (
    <section className="page golf">
      <div className="toolbar"><span className="grow" />
        <button type="button" className="secondary" onClick={() => openPanel('golffind', {})}>Find a course</button>
        <button type="button" className="primary" onClick={() => openPanel('golfnewround', {})}>Start a round</button>
      </div>
      {fresh && (
        <section className="card empty-start">
          <h2 className="home-card-title">Get set up</h2>
          <p className="small">Find your course (OpenStreetMap has most, with every hole drawn), fill your bag, then play a round on
            your phone - or type in a card after. Stableford points, your stats and a handicap estimate follow.</p>
          <div className="button-row">
            <button type="button" className="primary" onClick={() => openPanel('golffind', {})}>Find your course</button>
            {s.clubs === 0 && <button type="button" className="secondary" onClick={fillBag}>Fill your bag</button>}
            {s.courses > 0 && <button type="button" className="secondary" onClick={() => openPanel('golfnewround', {})}>Start a round</button>}
            <Link className="button plain" to="/golf/stats#golf-settings">Type your GA Handicap</Link>
          </div>
        </section>
      )}
      {s.playing.map((r) => (
        <section key={r.round_id} className="card golf-playing">
          <span className="stat-icon low" aria-hidden="true"><GolfIcon size={22} /></span>
          <span className="grow">
            <span className="item-title">Playing now: {r.course_name}</span>
            <span className="item-meta">{shortDate(r.played_on)} · {r.entered} of {r.of} holes in
              {r.entered > 0 && r.format === 'Stableford' && ` · ${r.points} pts`}</span>
          </span>
          <span className="button-row">
            <button type="button" className="primary" onClick={() => navigate(`/golf/play?round=${r.round_id}`)}>Resume</button>
            <button type="button" className="plain" onClick={() => openPanel('golfround', { id: r.round_id })}>Scorecard</button>
          </span>
        </section>
      ))}
      {(h.current != null || s.rounds > 0) && (
        <section className="card golf-hcp-hero">
          <div className="golf-hcp-hero-main">
            <span className="golf-hcp-hero-label">{h.source === 'official' ? 'GA Handicap' : 'Handicap'}
              {h.source === 'estimate' && <span className="pill low">estimate</span>}</span>
            <strong className="golf-hcp-hero-number">{hcpText(h.current)}</strong>
            <span className="muted small">
              {h.source === 'official' ? (h.official_as_of ? `From GolfLink, as of ${shortDate(h.official_as_of)}` : 'From GolfLink')
                : h.source === 'estimate' ? `Best ${h.best} of your last ${h.of} differentials`
                  : `${h.counting} of 3 counting rounds for an estimate`}
              {h.source === 'official' && h.estimate != null && ` · the app's estimate: ${hcpText(h.estimate)}`}
            </span>
            {homeTee && (
              <span className="golf-hcp-hero-daily">Daily handicap at {home.name} ({homeTee.name}): <strong>{homeTee.daily_handicap}</strong></span>
            )}
            {!homeId && s.courses > 0 && <Link className="small" to="/golf/stats#golf-settings">Set your home course for a daily handicap</Link>}
          </div>
          <div className="golf-hcp-hero-line"><HandicapLine history={s.handicap_trend} height={120} /></div>
          <dl className="golf-hcp-hero-year">
            <div><dt>Rounds in {s.year}</dt><dd>{s.this_year.rounds}</dd></div>
            <div><dt>Holes</dt><dd>{s.this_year.holes}</dd></div>
            <div><dt>Practice</dt><dd>{plural(s.this_year.practice.sessions, 'session')}</dd></div>
          </dl>
        </section>
      )}
      {s.rounds > 0 && (
        <div className="home-grid">
          <div className="home-stack">
            <section className="card home-card">
              <div className="section-head">
                <h2 className="home-card-title">Last rounds</h2>
                <button type="button" className="plain small" onClick={() => openPanel('golfnewround', {})}>+ New round</button>
              </div>
              <ul className="list plain-list">{s.recent.map((r) => <RoundRow key={r.round_id} r={r} />)}</ul>
              <Link className="button plain small" to="/golf/rounds">All rounds →</Link>
            </section>
            {s.best.length > 0 && (
              <section className="card home-card">
                <h2 className="home-card-title">Best rounds</h2>
                <ul className="list plain-list">{s.best.map((r) => <RoundRow key={r.round_id} r={r} />)}</ul>
              </section>
            )}
          </div>
          <div className="home-stack">
            <section className="card home-card">
              <h2 className="home-card-title">Plays like</h2>
              <PlaysLike stats={s.stats} bench={s.bench} target={s.target} />
              <Link className="button plain small" to="/golf/stats">Every stat →</Link>
            </section>
            {scores.length > 1 && (
              <section className="card home-card">
                <h2 className="home-card-title">Scoring trend</h2>
                <LineChart title="Gross score (18 holes)" rows={scores} valueLabel="strokes" height={160} stepChoices={GOLF_STEPS} />
              </section>
            )}
          </div>
        </div>
      )}
      {s.rounds > 0 && (
        <div className="home-stats">
          <Stat to="/golf/courses" Icon={GolfIcon} tone="ok" value={s.courses} label="Courses" sub="maps, tees and how you play each hole" />
          <Stat to="/golf/bag" Icon={TargetIcon} tone="teal" value={s.clubs} label="Clubs in the bag" sub="and how far each goes" />
          <Stat to="/golf/practice" Icon={TrophyIcon} tone="low" value={s.this_year.practice.minutes} label={`Practice minutes in ${s.year}`}
            sub={plural(s.this_year.practice.sessions, 'session')} />
        </div>
      )}
    </section>
  )
}

export function RoundsView() {
  const { refreshKey, openPanel } = useApp()
  const courses = useGolfCourses()
  const [course, setCourse] = useState('')
  const [year, setYear] = useState('')
  const [rows, setRows] = useState(null)
  useEffect(() => {
    api.golfRounds({ course_id: course, year }).then(setRows).catch(() => setRows([]))
  }, [course, year, refreshKey])
  const thisYear = new Date().getFullYear()
  return (
    <section className="page golf">
      <div className="toolbar">
        <select value={course} onChange={(e) => setCourse(e.target.value)} aria-label="Course">
          <option value="">Every course</option>
          {(courses ?? []).map((c) => <option key={c.course_id} value={c.course_id}>{c.name}</option>)}
        </select>
        <select value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year">
          <option value="">Every year</option>
          {[0, 1, 2, 3, 4, 5].map((i) => <option key={i} value={thisYear - i}>{thisYear - i}</option>)}
        </select>
        <span className="grow" />
        <button type="button" className="primary" onClick={() => openPanel('golfnewround', {})}>+ New round</button>
      </div>
      {!rows ? <p className="muted loading">Loading...</p> : rows.length === 0 ? (
        course || year ? <p className="empty card">No rounds match that.</p> : (
          <EmptyState Icon={GolfIcon} title="No rounds yet" action="Start a round" onAction={() => openPanel('golfnewround', {})}>
            Play one on your phone (distances to the green, your score as you go) or type in a card afterwards.</EmptyState>
        )
      ) : (
        <section className="card home-card">
          <p className="muted small golf-rounds-note">{plural(rows.length, 'round')}. "Counts": one of the best 8 differentials of your
            last 20 - the ones your handicap estimate is made of.</p>
          <ul className="list plain-list">{rows.map((r) => <RoundRow key={r.round_id} r={r} showCounted />)}</ul>
        </section>
      )}
    </section>
  )
}
