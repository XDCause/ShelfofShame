import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, shortDate } from '../../api.js'
import { ColumnChart } from '../../components/charts.jsx'
import { BallIcon, VideoIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { OUTCOMES, SCORE_NAMES, SKILLS, clipFilterName, nextRotation, percentText, resultText, trendText } from './vbHelpers.js'

// Volleyball's numbers you enter as you play: serve and pass ratings, rotations, clips tagged by skill and outcome,
// and drill results (api/app/vbstats.py, vbclips.py).

// In a game or training: tap each serve or pass (0-3), and, if you like, log each rally with its rotation.
export function GameTracker({ gameId }) {
  const [ratings, setRatings] = useState(null)
  const [points, setPoints] = useState(null)
  const [rotation, setRotation] = useState(1)
  const [serving, setServing] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    api.gameRatings(gameId).then(setRatings).catch((e) => setError(e.message))
    api.gamePoints(gameId).then(setPoints).catch((e) => setError(e.message))
  }, [gameId])
  const run = async (fn) => {
    setError('')
    try { await fn() } catch (e) { setError(e.message) }
  }
  if (!ratings || !points) return <section className="panel-section"><p className="muted small">{error || 'Loading...'}</p></section>
  const lastRating = ratings.entries[ratings.entries.length - 1]
  const lastPoint = points.points[points.points.length - 1]
  const rally = (won) => run(async () => {
    setPoints(await api.addPoint(gameId, { rotation, serving, won }))
    setRotation(nextRotation(rotation, serving, won))
    setServing(won)                  // win a rally and you serve the next; lose it and they do
  })
  return (
    <section className="panel-section vbm-tracker">
      <h3 className="section-title">Ratings</h3>
      <p className="hint">Tap a score after each serve or pass: 0 error, 1 poor, 2 ok, 3 perfect.</p>
      {['serve', 'pass'].map((skill) => (
        <div key={skill} className="vbm-rate-row">
          <span className="vbm-rate-name">{skill === 'serve' ? 'Serve' : 'Pass'}</span>
          <span className="vbm-rate-buttons" role="group" aria-label={`Rate a ${skill}`}>
            {SCORE_NAMES.map((name, score) => (
              <button key={score} type="button" className="secondary vbm-score" aria-label={`${skill} ${score}: ${name}`}
                onClick={() => run(async () => setRatings(await api.addRating(gameId, skill, score)))}>{score}</button>
            ))}
          </span>
          <span className="muted small">{ratings[skill].n ? `${ratings[skill].avg} avg · ${ratings[skill].n}` : 'none yet'}</span>
        </div>
      ))}
      {lastRating && (
        <button type="button" className="plain small" onClick={() => run(async () => setRatings(await api.deleteRating(lastRating.rating_id)))}>
          Undo last ({lastRating.skill} {lastRating.score})</button>
      )}

      <h3 className="section-title">Rallies by rotation <span className="muted small">(optional)</span></h3>
      <div className="vbm-rally">
        <span className="vbm-rate-buttons" role="group" aria-label="Your rotation">
          {[1, 2, 3, 4, 5, 6].map((r) => (
            <button key={r} type="button" className="secondary vbm-score" aria-pressed={rotation === r} onClick={() => setRotation(r)}>{r}</button>
          ))}
        </span>
        <span className="segmented" role="group" aria-label="Who served">
          <button type="button" aria-pressed={serving} onClick={() => setServing(true)}>We served</button>
          <button type="button" aria-pressed={!serving} onClick={() => setServing(false)}>They served</button>
        </span>
        <span className="button-row">
          <button type="button" className="primary" onClick={() => rally(true)}>We won it</button>
          <button type="button" className="secondary" onClick={() => rally(false)}>We lost it</button>
        </span>
      </div>
      {points.points.length > 0 && (
        <>
          <RotationTable rows={points.rotations} />
          <button type="button" className="plain small" onClick={() => run(async () => setPoints(await api.deletePoint(lastPoint.point_id)))}>
            Undo last rally</button>
        </>
      )}
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

// Side-out % (rallies won when they served) and points won when you served, for each rotation.
export function RotationTable({ rows }) {
  const seen = rows.filter((r) => r.serving + r.receiving > 0)
  if (seen.length === 0) return <p className="muted small">No rallies logged yet.</p>
  return (
    <table className="vbm-table">
      <caption className="muted small">Side-out % = rallies won when they served. Points on serve = rallies won when you served.</caption>
      <thead><tr><th scope="col">Rotation</th><th scope="col">Side-out</th><th scope="col">Points on serve</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.rotation}>
            <th scope="row">{r.rotation}</th>
            <td>{percentText(r.side_out_percent)} <span className="muted small">{r.receiving ? `${r.side_outs}/${r.receiving}` : ''}</span></td>
            <td>{percentText(r.point_percent)} <span className="muted small">{r.serving ? `${r.points_won}/${r.serving}` : ''}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// Volleyball numbers: rating averages and trend, rotations, and your tagged clips by skill and outcome.
export function VbStatsView() {
  const { refreshKey } = useApp()
  const [ratings, setRatings] = useState(null)
  const [rot, setRot] = useState(null)
  const [clips, setClips] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.ratingsSummary().then(setRatings).catch((e) => setError(e.message))
    api.rotationStats().then(setRot).catch((e) => setError(e.message))
    api.taggedClips().then(setClips).catch((e) => setError(e.message))
  }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!ratings || !rot || !clips) return <p className="muted loading">Loading...</p>
  const count = (skill, outcome) => clips.counts.filter((c) => c.skill === skill && c.outcome === outcome).reduce((n, c) => n + c.n, 0)
  const tagged = clips.counts.filter((c) => c.skill).reduce((n, c) => n + c.n, 0)
  return (
    <section className="page stats">
      <div className="home-grid">
        {['serve', 'pass'].map((skill) => {
          const r = ratings[skill]
          return (
            <section key={skill} className="card home-card">
              <h2 className="home-card-title">{skill === 'serve' ? 'Serving' : 'Passing'}</h2>
              {r.n === 0 ? <p className="muted small">Rate {skill}s in a game or training (open it, tap 0-3) and the average shows here.</p> : (
                <>
                  <p><strong className="vbm-avg">{r.avg}</strong> <span className="muted small">out of 3 · {r.n} {skill}s</span></p>
                  <p className="small">{trendText(r.trend)}</p>
                  <ColumnChart title="Score" valueLabel="times" labelValues
                    rows={SCORE_NAMES.map((name, i) => ({ label: `${i} ${name}`, value: r.counts[i] }))} />
                  {r.games.length > 1 && (
                    <>
                      <h3 className="section-title">Average per game</h3>
                      <ColumnChart title="Game" valueLabel="average (0-3)" height={140}
                        rows={r.games.slice(-12).map((g) => ({ label: shortDate(g.played_on), value: g.avg, tip: `${g.n} ${skill}s` }))} />
                    </>
                  )}
                </>
              )}
            </section>
          )
        })}
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Rotations</h2>
          {rot.rallies === 0 ? <p className="muted small">Log rallies in a game (open it, pick the rotation, tap We won / We lost) to see side-out % for each rotation.</p> : (
            <>
              <p className="small">Side-out {percentText(rot.side_out_percent)} · points on serve {percentText(rot.point_percent)} · {rot.rallies} rallies in {rot.games} games</p>
              <RotationTable rows={rot.rotations} />
            </>
          )}
        </section>
        <section className="card home-card wide-card">
          <h2 className="home-card-title">Clips by skill</h2>
          {tagged === 0 ? <p className="muted small">Tag clips with a skill and good / error (in a video's clips) to find them from here.</p> : (
            <ul className="vbm-skill-links">
              {SKILLS.filter((s) => count(s, 'good') + count(s, 'error') > 0).map((s) => (
                <li key={s}>
                  <strong>{s.charAt(0).toUpperCase() + s.slice(1)}</strong>{' '}
                  <Link to={`/volleyball/clips?skill=${s}&outcome=good`}>{count(s, 'good')} good</Link>{' · '}
                  <Link to={`/volleyball/clips?skill=${s}&outcome=error`}>{count(s, 'error')} errors</Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  )
}

// Clips tagged by skill and outcome, filterable ("my serve errors"); the address can carry the filter (?skill=serve&outcome=error).
export function ClipsView() {
  const { refreshKey, openPanel } = useApp()
  const params = new URLSearchParams(window.location.search)
  const [skill, setSkill] = useState(SKILLS.includes(params.get('skill')) ? params.get('skill') : '')
  const [outcome, setOutcome] = useState(['good', 'error'].includes(params.get('outcome')) ? params.get('outcome') : '')
  const [data, setData] = useState(null)
  const [playing, setPlaying] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.taggedClips({ skill, outcome }).then(setData).catch((e) => setError(e.message)) }, [skill, outcome, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  return (
    <section className="page">
      <div className="chip-row scroll" role="group" aria-label="Skill">
        <button type="button" className="chip-filter" aria-pressed={skill === ''} onClick={() => setSkill('')}>All skills</button>
        {SKILLS.map((s) => <button key={s} type="button" className="chip-filter" aria-pressed={skill === s} onClick={() => setSkill(s)}>{s}</button>)}
      </div>
      <div className="chip-row" role="group" aria-label="Outcome">
        <button type="button" className="chip-filter" aria-pressed={outcome === ''} onClick={() => setOutcome('')}>Any outcome</button>
        {OUTCOMES.map(([v, l]) => <button key={v} type="button" className="chip-filter" aria-pressed={outcome === v} onClick={() => setOutcome(v)}>{l}</button>)}
      </div>
      <h2 className="home-card-title">{clipFilterName(skill, outcome)}{data && <span className="muted small"> · {data.clips.length}</span>}</h2>
      {!data ? <p className="muted loading">Loading...</p> : data.clips.length === 0 ? (
        <EmptyState Icon={VideoIcon} title="No clips match">Tag clips in a video (Videos → open a video → Clips) with a skill and good / error.</EmptyState>
      ) : (
        <ul className="vbm-clips">
          {data.clips.map((c) => (
            <li key={c.clip_id} className="card">
              <div className="section-head">
                <span className="grow">
                  <span className="item-title">{c.title ?? 'Clip'}</span>
                  <span className="item-meta">{c.video_title}{c.game_day && ` · ${shortDate(c.game_day)}`}</span>
                </span>
                {c.skill && <span className="pill tint">{c.skill}</span>}
                {c.outcome && <span className={`pill ${c.outcome === 'error' ? 'out' : 'ok'}`}>{c.outcome}</span>}
              </div>
              {playing === c.clip_id && c.file_url ? (
                <video className="video-player" src={`${c.file_url}#t=${c.start},${c.end}`} controls autoPlay playsInline />
              ) : (
                <div className="button-row">
                  {c.file_url && <button type="button" className="secondary small" onClick={() => setPlaying(c.clip_id)}>▶ Play clip</button>}
                  <button type="button" className="plain small" onClick={() => openPanel('video', { id: c.video_id })}>Open the video</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// Drills: your best and how much you did each week.
export function DrillsView() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => api.drillStats().then(setData).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load, refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const weeks = data.weeks.map((w) => ({ label: shortDate(w.week), value: w.reps, tip: `${w.sessions} sessions · ${w.minutes} min` }))
  return (
    <section className="page">
      {data.drills.length === 0 ? (
        <EmptyState Icon={BallIcon} title="No drills yet">Add drills in Coach (a note of kind Drill), then log how each one went here.</EmptyState>
      ) : (
        <>
          <section className="card home-card wide-card">
            <h2 className="home-card-title">Reps each week</h2>
            {data.weeks.some((w) => w.reps || w.minutes) ? <ColumnChart title="Week starting" valueLabel="reps" rows={weeks} labelValues />
              : <p className="muted small">Log a drill with how many you did and the weeks fill in.</p>}
          </section>
          <ul className="vbm-drills">{data.drills.map((d) => <DrillCard key={d.note_id} drill={d} onChanged={load} />)}</ul>
        </>
      )}
    </section>
  )
}

function DrillCard({ drill: d, onChanged }) {
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ result: '', reps: '', minutes: '' })
  const [label, setLabel] = useState(d.result_label ?? '')
  const [lower, setLower] = useState(d.lower_is_better)
  const [error, setError] = useState('')
  const [detail, setDetail] = useState(null)
  const run = async (fn) => {
    setError('')
    try { await fn(); onChanged(); if (open) setDetail(await api.drillLogs(d.note_id)) } catch (e) { setError(e.message) }
  }
  const toggle = async () => {
    setOpen(!open)
    if (!open && !detail) setDetail(await api.drillLogs(d.note_id).catch(() => null))
  }
  const num = (v) => (v === '' ? null : Number(v))
  const submit = (e) => {
    e.preventDefault()
    run(async () => { await api.addDrillLog(d.note_id, { result: num(f.result), reps: num(f.reps), minutes: num(f.minutes) }); setF({ result: '', reps: '', minutes: '' }) })
  }
  return (
    <li className="card vbm-drill">
      <button type="button" className="row-button" onClick={toggle} aria-expanded={open}>
        <span className="grow"><span className="item-title">{d.title}</span>
          <span className="item-meta">{d.sessions ? `${d.sessions} sessions · ${d.reps.toLocaleString()} reps · ${d.minutes} min` : 'not logged yet'}</span></span>
        <span className="vbm-best">{d.best != null ? <><span className="muted small">Best </span><strong>{resultText(d.best, d.result_label)}</strong></> : null}</span>
      </button>
      {open && (
        <div className="vbm-drill-body">
          <form className="button-row" onSubmit={submit}>
            <label className="small">Result <input type="number" min="0" step="any" value={f.result} onChange={(e) => setF({ ...f, result: e.target.value })} /></label>
            <label className="small">Reps <input type="number" min="1" value={f.reps} onChange={(e) => setF({ ...f, reps: e.target.value })} /></label>
            <label className="small">Minutes <input type="number" min="1" value={f.minutes} onChange={(e) => setF({ ...f, minutes: e.target.value })} /></label>
            <button type="submit" className="primary small">Log it</button>
          </form>
          <form className="button-row" onSubmit={(e) => { e.preventDefault(); run(() => api.setDrillResult(d.note_id, { result_label: label, lower_is_better: lower })) }}>
            <label className="small">What the result counts <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="in a row, out of 20, seconds" maxLength={40} /></label>
            <label className="small"><input type="checkbox" checked={lower} onChange={(e) => setLower(e.target.checked)} /> Lower is better (a time)</label>
            <button type="submit" className="secondary small">Save</button>
          </form>
          {detail?.logs.length > 0 && (
            <ul className="vbm-log-list">
              {detail.logs.slice(0, 15).map((l) => (
                <li key={l.log_id}>
                  <span className="grow small">{shortDate(l.done_on)} · {[l.result != null && resultText(l.result, d.result_label), l.reps && `${l.reps} reps`, l.minutes && `${l.minutes} min`].filter(Boolean).join(' · ')}</span>
                  <button type="button" className="icon-btn" aria-label={`Remove the log on ${shortDate(l.done_on)}`}
                    onClick={() => run(() => api.deleteDrillLog(l.log_id))}>✕</button>
                </li>
              ))}
            </ul>
          )}
          {error && <p className="alert error small">{error}</p>}
        </div>
      )}
    </li>
  )
}
