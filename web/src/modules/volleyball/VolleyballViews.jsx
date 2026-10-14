import { useEffect, useState } from 'react'
import { api, clock, dayDate, shortDate } from '../../api.js'
import { BallIcon, CalendarIcon, ShoeIcon, VideoIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'
import { gameTitle, resultTone, score, youtubeId } from './VolleyballPanels.jsx'

const GEAR_TONE = { New: 'ok', Good: 'ok', Worn: 'low', 'Needs replacing': 'out', Retired: '' }

function useVolleyball() {
  const { refreshKey } = useApp()
  return useShared(`volleyball-${refreshKey}`, () => Promise.all([api.volleyballSummary(), api.upcoming(20)])
    .then(([summary, upcoming]) => ({ summary, next: upcoming.filter((e) => e.hobby === 'volleyball') })))
}

// Games and training: this year's record, the next one on the calendar, then every game.
export function GamesView() {
  const { refreshKey, openPanel } = useApp()
  const { data } = useVolleyball()
  const [games, setGames] = useState(null)
  const [teams, setTeams] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    api.listVolleyball().then(setGames).catch((e) => setError(e.message))
    api.volleyballTeams().then((t) => setTeams(t.teams)).catch((e) => setError(e.message))
  }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!games || !data || !teams) return <p className="muted loading">Loading...</p>
  const { summary, next } = data

  return (
    <section className="page">
      <div className="stat-grid card">
        <div><span>Games this year</span><strong>{summary.games}</strong></div>
        <div><span>Won – lost</span><strong>{summary.won}–{summary.lost}</strong></div>
        <div><span>Training</span><strong>{summary.trainings}</strong></div>
      </div>
      {next.length > 0 && (
        <button type="button" className="card next-up" onClick={() => openPanel('event', { id: next[0].event_id, day: next[0].day })}>
          <span className="stat-icon tint"><CalendarIcon size={22} /></span>
          <span className="grow">
            <span className="muted small">Next up</span>
            <span className="item-title">{next[0].title}</span>
            <span className="item-meta">{dayDate(next[0].day).toLocaleDateString('en-AU', { weekday: 'long', day: 'numeric', month: 'short' })}
              {next[0].start_time && ` · ${clock(next[0].start_time)}`}{next[0].location && ` · ${next[0].location}`}</span>
          </span>
        </button>
      )}
      <section className="card teams-card" aria-label="Your teams">
        <div className="section-head">
          <h2 className="home-card-title">Your teams</h2>
          <button type="button" className="plain small" onClick={() => openPanel('vbteam', {})}>+ Add team</button>
        </div>
        {teams.length === 0 ? (
          <p className="muted small">Add the team you play in and where it plays - new games then start with both filled in.</p>
        ) : (
          <ul className="team-chips">
            {teams.map((t) => (
              <li key={t.team_id}>
                <button type="button" className={t.retired ? 'team-chip retired' : 'team-chip'} onClick={() => openPanel('vbteam', { id: t.team_id })}>
                  <strong>{t.name}</strong>{t.is_default && <span className="pill tint">Default</span>}{t.retired && <span className="pill">Retired</span>}
                  <span className="muted small">{[t.location, `${t.games} game${t.games === 1 ? '' : 's'}`].filter(Boolean).join(' · ')}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <div className="toolbar">
        <p className="summary grow"><strong>{games.length}</strong> logged</p>
        <button type="button" className="secondary" onClick={() => openPanel('event', { id: null, hobby: 'volleyball', title: 'Volleyball' })}>Plan a game</button>
        <button type="button" className="primary" onClick={() => openPanel('volleyball', {})}>+ Log a game</button>
      </div>
      {games.length === 0 ? (
        <p className="empty card">No games yet. Put your comp night on the calendar (Plan a game, repeating weekly), then log each result.</p>
      ) : (
        <ul className="journal-cards">
          {games.map((g) => {
            const d = dayDate(g.played_on)
            return (
              <li key={g.game_id}>
                <button type="button" className="journal-card" onClick={() => openPanel('volleyball', { id: g.game_id })}>
                  <span className="date-block" aria-label={shortDate(g.played_on)}>
                    <strong>{d.getDate()}</strong><span>{d.toLocaleDateString('en-AU', { month: 'short' })}</span><span>{d.getFullYear()}</span>
                  </span>
                  <span className="grow">
                    <span className="journal-card-head">
                      <span className="item-title">{gameTitle(g)}</span>
                      {score(g) ? <span className={`pill ${resultTone(g.result)}`}>{score(g)}</span>
                        : <span className="pill">{g.kind}</span>}
                    </span>
                    <span className="item-meta">{[g.team, g.venue, g.videos && `${g.videos} video${g.videos === 1 ? '' : 's'}`].filter(Boolean).join(' · ')}</span>
                    {g.notes && <span className="page-snippet two-lines">{g.notes}</span>}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

// Your gear, worst condition first.
export function GearView() {
  const { refreshKey, openPanel } = useApp()
  const [gear, setGear] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.listGear().then(setGear).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!gear) return <p className="muted loading">Loading...</p>
  return (
    <section className="page">
      <div className="toolbar">
        <p className="summary grow"><strong>{gear.filter((g) => g.condition !== 'Retired').length}</strong> in use
          {gear.some((g) => g.condition === 'Needs replacing') && <span className="muted"> · {gear.filter((g) => g.condition === 'Needs replacing').length} to replace</span>}</p>
        <button type="button" className="primary" onClick={() => openPanel('gear', {})}>+ Add gear</button>
      </div>
      {gear.length === 0 ? <p className="empty card">No gear yet. Shoes, knee pads, your own ball...</p> : (
        <div className="model-grid">
          {gear.map((g) => (
            <button key={g.gear_id} type="button" className="model-card" onClick={() => openPanel('gear', { id: g.gear_id })}>
              <span className="model-photo">
                {g.photo_url ? <img src={g.photo_url} alt="" loading="lazy" />
                  : <span className="photo-missing big-icon"><ShoeIcon size={44} /></span>}
                <span className={`status-badge pill ${GEAR_TONE[g.condition]}`}>{g.condition}</span>
              </span>
              <span className="model-body">
                <span className="model-name">{g.name}</span>
                <span className="model-meta">{[g.kind, g.brand, g.size].filter(Boolean).join(' · ')}</span>
                {g.purchase_date && <span className="muted small">Bought {shortDate(g.purchase_date)}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

// Video links: not watched first. YouTube links show their thumbnail.
export function VideosView() {
  const { refreshKey, openPanel, changed } = useApp()
  const [videos, setVideos] = useState(null)
  const [topic, setTopic] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api.listVideos().then(setVideos).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!videos) return <p className="muted loading">Loading...</p>
  const topics = [...new Set(videos.map((v) => v.topic).filter(Boolean))]
  const visible = videos.filter((v) => !topic || v.topic === topic)
  const watched = async (v) => {
    setVideos((vs) => vs.map((x) => (x.video_id === v.video_id ? { ...x, watched: !v.watched } : x)))
    try { await api.updateVideo(v.video_id, { watched: !v.watched }); changed() } catch (e) { setError(e.message) }
  }

  return (
    <section className="page">
      <div className="toolbar">
        <div className="chip-row scroll" role="group" aria-label="Topic">
          {topics.length > 1 && ['', ...topics].map((t) => (
            <button key={t || 'all'} type="button" className="chip-filter" aria-pressed={topic === t} onClick={() => setTopic(t)}>
              {t || 'All'}
            </button>
          ))}
        </div>
        <button type="button" className="primary" onClick={() => openPanel('video', {})}>+ Add video</button>
      </div>
      {visible.length === 0 ? <p className="empty card">No videos yet. Add links to game footage or drills you want to learn.</p> : (
        <ul className="video-grid">
          {visible.map((v) => {
            const yt = youtubeId(v.url)
            return (
              <li key={v.video_id} className={v.watched ? 'video-card watched' : 'video-card'}>
                <a href={v.url} target="_blank" rel="noreferrer" className="video-thumb">
                  {yt ? <img src={`https://img.youtube.com/vi/${yt}/mqdefault.jpg`} alt="" loading="lazy" referrerPolicy="no-referrer" />
                    : <span className="photo-missing big-icon"><VideoIcon size={40} /></span>}
                </a>
                <div className="video-body">
                  <a href={v.url} target="_blank" rel="noreferrer" className="item-title">{v.title} ↗</a>
                  <span className="item-meta">{[v.topic, v.game_day && `${shortDate(v.game_day)}${v.game_opponent ? ` vs ${v.game_opponent}` : ''}`].filter(Boolean).join(' · ')}</span>
                  <span className="button-row">
                    <label className="tick-label"><input type="checkbox" checked={v.watched} onChange={() => watched(v)} /> Watched</label>
                    <button type="button" className="plain small" onClick={() => openPanel('video', { id: v.video_id })}>Edit</button>
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

// Home: two tiles.
export function VolleyballTiles() {
  const { data } = useVolleyball()
  if (!data) return <><StatSkeleton /><StatSkeleton /></>
  const { summary, next } = data
  const n = next[0]
  return (
    <>
      <Stat to="/volleyball/games" Icon={BallIcon} tone="low" value={`${summary.won}–${summary.lost}`} label="Volleyball"
        sub={`won–lost this year`} />
      <Stat to="/calendar" Icon={CalendarIcon} tone="teal"
        value={n ? dayDate(n.day).toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric' }) : '—'}
        label="Next game" sub={n ? [clock(n.start_time), n.location].filter(Boolean).join(' · ') || n.title : 'nothing planned'} />
    </>
  )
}
