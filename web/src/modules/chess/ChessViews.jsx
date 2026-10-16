import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api, shortDate } from '../../api.js'
import { LineChart } from '../../components/charts.jsx'
import Fold from '../../components/Fold.jsx'
import { ChessIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { Change, StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'
import { CLASSES, ChessSetup, ChessSyncBar, OtbForm, RatingChange, ResultPill, className, useChessAccount } from './chessParts.jsx'

// The Chess hobby's pages: a dashboard (ratings, the rating over time, this week, recent games),
// every game (filters, over-the-board games added here), and your openings.

const useChessSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`chess-summary-${refreshKey}`, () => api.chessSummary())
}

// One game in a list: result, opponent, what kind of game, the rating change.
function GameRow({ game: g }) {
  const { openPanel } = useApp()
  return (
    <li>
      <button type="button" className="row-button chess-row" onClick={() => openPanel('chessgame', { id: g.game_id })}>
        <span className={`chess-colour ${g.colour}`} title={`You played ${g.colour}`} aria-label={`You played ${g.colour}`} />
        <span className="grow">
          <span className="item-title"><ResultPill game={g} short /> vs {g.opp_name}{g.opp_rating && <span className="muted"> ({g.opp_rating})</span>}</span>
          <span className="item-meta">
            {className(g.time_class)}{g.source === 'otb' && ' · over the board'}{g.opening && ` · ${g.opening}`}
            {g.event && ` · ${g.event}`} · {shortDate(g.played_at)}
          </span>
        </span>
        <span className="chess-rating">
          {g.my_rating && <strong>{g.my_rating}</strong>}
          <RatingChange value={g.rating_change} />
          {g.accuracy != null && <span className="muted small" title="Your accuracy (chess.com)">{Number(g.accuracy).toFixed(1)}%</span>}
        </span>
      </button>
    </li>
  )
}

export function Dashboard() {
  const { account, setAccount, error } = useChessAccount()
  const { data: s } = useChessSummary()
  const navigate = useNavigate()
  if (error) return <p className="alert error">{error}</p>
  if (!account) return <p className="muted loading">Loading...</p>
  if (!account.username) return <section className="page"><ChessSetup setAccount={setAccount} /></section>
  return (
    <section className="page chess">
      <ChessSyncBar account={account} setAccount={setAccount} />
      {!s ? <p className="muted loading">Loading...</p> : (
        <>
          <div className="home-stats">
            {s.classes.map((c) => (
              <Stat key={c.time_class} to={`/chess/games?time_class=${c.time_class}`} Icon={ChessIcon} tone={c.time_class === s.main ? 'tint' : 'purple'}
                value={c.rating ?? '—'} label={className(c.time_class)} change={c.week_change != null && <Change value={c.week_change} />}
                sub={`${c.best ? `best ${c.best} · ` : ''}${c.record.win}–${c.record.loss}–${c.record.draw}`} />
            ))}
            {s.puzzles.highest && <Stat to="/chess/dashboard" Icon={TrophyIcon} tone="ok" value={s.puzzles.highest} label="Puzzles (best)"
              sub={s.puzzles.rush_best ? `Puzzle Rush best ${s.puzzles.rush_best}` : 'chess.com puzzles'} />}
            <Stat to="/chess/games" Icon={ChessIcon} tone="teal" value={s.week.games} label="Games this week"
              sub={`${s.week.win} won · ${s.week.loss} lost · ${s.week.draw} drawn`} />
          </div>
          {/* Left: the rating chart with Over the board under it; right: recent games (the tall one). */}
          <div className="home-grid">
            <div className="home-stack">
              <RatingCard classes={s.classes.map((c) => c.time_class)} main={s.main} />
              <section className="card home-card">
                <h2 className="home-card-title">Over the board</h2>
                <p className="muted small">{s.otb_games ? `${s.otb_games} game${s.otb_games === 1 ? '' : 's'} logged.` : 'Club nights and tournaments, logged by hand.'}</p>
                <button type="button" className="secondary" onClick={() => navigate('/chess/games?add=1')}>+ Log a game</button>
              </section>
            </div>
            <section className="card home-card">
              <h2 className="home-card-title">Recent games</h2>
              {s.recent.length === 0 ? <p className="muted small">No games yet.</p> : (
                <ul className="list plain-list">{s.recent.map((g) => <GameRow key={g.game_id} game={g} />)}</ul>
              )}
              <Link className="button plain small" to="/chess/games">All games →</Link>
            </section>
          </div>
        </>
      )}
    </section>
  )
}

const RANGES = [[90, '3 months'], [365, 'Year'], [5000, 'All']]

// Your rating over time, one time control at a time.
function RatingCard({ classes, main }) {
  const { refreshKey } = useApp()
  const [tc, setTc] = useState(main)
  const [days, setDays] = useState(365)
  const [series, setSeries] = useState(null)
  useEffect(() => { api.chessRatings(days).then(setSeries).catch(() => setSeries({})) }, [days, refreshKey])
  const rows = (series?.[tc] ?? []).map((r) => ({ x: String(r.day).slice(0, 10), y: r.rating }))
  return (
    <section className="card home-card wide-card">
      <div className="chess-chart-head">
        <h2 className="home-card-title">{className(tc)} rating</h2>
        <div className="segmented" role="group" aria-label="Time control">
          {classes.filter((c) => c !== 'classical').map((c) => (
            <button key={c} type="button" aria-pressed={tc === c} onClick={() => setTc(c)}>{className(c)}</button>
          ))}
        </div>
        <div className="segmented" role="group" aria-label="Range">
          {RANGES.map(([d, label]) => <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}>{label}</button>)}
        </div>
      </div>
      {!series ? <p className="muted loading">Loading...</p> : <LineChart title={`${className(tc)} rating`} rows={rows} valueLabel="rating" />}
    </section>
  )
}

const RESULTS = [['', 'All'], ['win', 'Wins'], ['loss', 'Losses'], ['draw', 'Draws']]

// Every game: search, filters, newest first (100 at a time), and over-the-board games added here.
export function GamesView() {
  const { refreshKey, changed, openPanel } = useApp()
  const params = new URLSearchParams(window.location.search)
  const [f, setF] = useState({ time_class: params.get('time_class') ?? '', result: '', colour: '', source: '',
    opening: params.get('opening') ?? '', q: '' })
  const [adding, setAdding] = useState(params.get('add') === '1')
  const [data, setData] = useState(null)
  const [limit, setLimit] = useState(100)
  const [error, setError] = useState('')
  useEffect(() => {
    const t = setTimeout(() => api.chessGames({ ...f, limit }).then(setData).catch((e) => setError(e.message)), f.q ? 250 : 0)
    return () => clearTimeout(t)
  }, [f, limit, refreshKey])
  const set = (k, v) => { setF({ ...f, [k]: v }); setLimit(100) }
  if (error) return <p className="alert error">{error}</p>
  return (
    <section className="page">
      <div className="toolbar">
        <input type="search" className="search" value={f.q} onChange={(e) => set('q', e.target.value)}
          placeholder="Search opponents, openings, events..." aria-label="Search chess games" />
        <select value={f.colour} onChange={(e) => set('colour', e.target.value)} aria-label="Colour">
          <option value="">White and Black</option><option value="white">As White</option><option value="black">As Black</option>
        </select>
        <select value={f.source} onChange={(e) => set('source', e.target.value)} aria-label="Where">
          <option value="">Online and over the board</option><option value="chesscom">chess.com</option><option value="otb">Over the board</option>
        </select>
        <button type="button" className="secondary" onClick={() => setAdding(!adding)}>+ Log an over-the-board game</button>
      </div>
      <div className="chip-row scroll" role="group" aria-label="Time control">
        <button type="button" className="chip-filter" aria-pressed={!f.time_class} onClick={() => set('time_class', '')}>All</button>
        {CLASSES.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={f.time_class === id} onClick={() => set('time_class', id)}>{label}</button>
        ))}
        <span className="chip-gap" />
        {RESULTS.map(([id, label]) => (
          <button key={label} type="button" className="chip-filter" aria-pressed={f.result === id} onClick={() => set('result', id)}>{label}</button>
        ))}
      </div>
      {f.opening && <p className="small">Opening: <strong>{f.opening}</strong> <button type="button" className="plain small" onClick={() => set('opening', '')}>✕ Clear</button></p>}
      {adding && (
        <div className="card">
          <OtbForm game={null} onCancel={() => setAdding(false)} onSaved={(g) => { setAdding(false); changed(); openPanel('chessgame', { id: g.game_id }) }} />
        </div>
      )}
      {!data ? <p className="muted loading">Loading...</p> : data.games.length === 0 ? <p className="empty card">No games here.</p> : (
        <>
          <p className="muted small">{data.total.toLocaleString()} game{data.total === 1 ? '' : 's'}</p>
          <ul className="list chess-games">{data.games.map((g) => <GameRow key={g.game_id} game={g} />)}</ul>
          {data.games.length < data.total && <button type="button" className="secondary" onClick={() => setLimit(limit + 100)}>Show more</button>}
        </>
      )}
    </section>
  )
}

// How you do with each opening as White or Black: games, wins / draws / losses, your score.
export function OpeningsView() {
  const { refreshKey } = useApp()
  const navigate = useNavigate()
  const [colour, setColour] = useState('white')
  const [tc, setTc] = useState('')
  const [data, setData] = useState(null)
  useEffect(() => { api.chessOpenings(colour, tc).then(setData).catch(() => setData({ openings: [] })) }, [colour, tc, refreshKey])
  const most = useMemo(() => Math.max(1, ...(data?.openings ?? []).map((o) => o.games)), [data])
  return (
    <section className="page">
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Colour">
          {[['white', 'As White'], ['black', 'As Black']].map(([id, label]) => (
            <button key={id} type="button" aria-pressed={colour === id} onClick={() => setColour(id)}>{label}</button>
          ))}
        </div>
        <select value={tc} onChange={(e) => setTc(e.target.value)} aria-label="Time control">
          <option value="">Every time control</option>
          {CLASSES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
      </div>
      <p className="muted small">Score = wins plus half the draws. Openings are chess.com's names for the moves played.</p>
      {!data ? <p className="muted loading">Loading...</p> : data.openings.length === 0 ? <p className="empty card">No games with this colour yet.</p> : (
        <div className="openings">
          {data.openings.map((o) => (
            <Fold key={o.name} className="opening" title={<><span className="opening-name">{o.name}</span><WdlBar o={o} most={most} /></>}
              detail={<>{o.games} game{o.games === 1 ? '' : 's'} · <strong>{Number(o.score)}%</strong></>}>
              <ul className="list compact">
                {o.variations.map((v) => (
                  <li key={v.name} className="opening-variation">
                    <span className="grow">{v.name}</span>
                    <span className="muted small">{v.wins}–{v.draws}–{v.losses} · {Number(v.score)}%{v.avg_opponent && ` · vs ${v.avg_opponent}`}</span>
                  </li>
                ))}
              </ul>
              <button type="button" className="plain small" onClick={() => navigate(`/chess/games?opening=${encodeURIComponent(o.name)}`)}>
                See these games →</button>
            </Fold>
          ))}
        </div>
      )}
    </section>
  )
}

// Wins / draws / losses as one bar (its length = how often you play it), with the numbers.
function WdlBar({ o, most }) {
  return (
    <span className="wdl" title={`${o.wins} won, ${o.draws} drawn, ${o.losses} lost`}>
      <span className="wdl-bar" style={{ width: `${Math.max(12, (100 * o.games) / most)}%` }} aria-hidden="true">
        <span className="wdl-win" style={{ flexGrow: o.wins }} />
        <span className="wdl-draw" style={{ flexGrow: o.draws }} />
        <span className="wdl-loss" style={{ flexGrow: o.losses }} />
      </span>
      <span className="wdl-text">{o.wins}–{o.draws}–{o.losses}</span>
    </span>
  )
}

// Home: your main rating and this week.
export function ChessTiles() {
  const { data: s } = useChessSummary()
  if (!s) return <StatSkeleton />
  if (!s.username) return null
  const main = s.classes.find((c) => c.time_class === s.main)
  return (
    <>
      {main && <Stat to="/chess/dashboard" Icon={ChessIcon} tone="tint" value={main.rating ?? '—'} label={`${className(main.time_class)} rating`}
        change={main.week_change != null && <Change value={main.week_change} />} sub={`${s.week.games} game${s.week.games === 1 ? '' : 's'} this week`} />}
    </>
  )
}
