import { useEffect, useState } from 'react'
import { api, timeAgo, today } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Small pieces the chess pages share: results, rating changes, time controls, the over-the-board
// form, the chess.com account and its sync.

export const CLASSES = [['bullet', 'Bullet'], ['blitz', 'Blitz'], ['rapid', 'Rapid'], ['daily', 'Daily'], ['classical', 'Classical']]
export const className = (tc) => Object.fromEntries(CLASSES)[tc] ?? tc

const HOW = {
  checkmated: 'checkmate', resigned: 'resignation', timeout: 'time', abandoned: 'abandoned', agreed: 'agreement',
  repetition: 'repetition', stalemate: 'stalemate', insufficient: 'insufficient material', '50move': '50-move rule',
  timevsinsufficient: 'time vs insufficient material', kingofthehill: 'king of the hill', threecheck: 'three check',
}

// "Won by resignation" / "Lost on time" / "Draw by agreement" - a green / red / grey pill.
export function ResultPill({ game: g, short = false }) {
  const how = HOW[g.how] ?? g.how
  const text = short ? { win: 'Won', loss: 'Lost', draw: 'Draw' }[g.result]
    : g.result === 'draw' ? `Draw${how ? ` by ${how}` : ''}`
      : `${g.result === 'win' ? 'Won' : 'Lost'}${how === 'time' ? ' on time' : how ? ` by ${how}` : ''}`
  return <span className={`pill result-${g.result} ${g.result === 'win' ? 'ok' : g.result === 'loss' ? 'out' : ''}`}>{text}</span>
}

// "+12" / "−8" after a game: how much your rating moved (same time control).
export function RatingChange({ value }) {
  if (value == null || value === 0) return null
  return <span className={value > 0 ? 'rating-up' : 'rating-down'}>{value > 0 ? `+${value}` : `−${-value}`}</span>
}

// chess.com's "180+2" -> "3 min + 2 s"; "1/86400" -> "1 day a move"; "600" -> "10 min".
export function timeControl(tc) {
  if (!tc) return ''
  if (tc.includes('/')) {
    const days = Number(tc.split('/')[1]) / 86400
    return `${days} day${days === 1 ? '' : 's'} a move`
  }
  const [base, inc] = tc.split('+').map(Number)
  const mins = base >= 60 ? `${base / 60} min` : `${base} s`
  return inc ? `${mins} + ${inc} s` : mins
}

// An over-the-board game: add one (game = null) or change one.
export function OtbForm({ game, onSaved, onCancel }) {
  const [f, setF] = useState(() => ({
    played_on: game ? String(game.played_at).slice(0, 10) : today(), time_class: game?.time_class ?? 'classical',
    colour: game?.colour ?? 'white', opp_name: game?.opp_name ?? '', opp_rating: game?.opp_rating ?? '',
    my_rating: game?.my_rating ?? '', result: game?.result ?? 'win', rated: game?.rated ?? false,
    event: game?.event ?? '', opening: game?.opening ?? '', pgn: game?.pgn ?? '', notes: game?.notes ?? '',
  }))
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const save = async (e) => {
    e.preventDefault()
    setError('')
    const body = { ...f, opp_rating: f.opp_rating === '' ? null : Number(f.opp_rating), my_rating: f.my_rating === '' ? null : Number(f.my_rating) }
    try {
      onSaved(game ? await api.updateChessGame(game.game_id, body) : await api.addChessGame(body))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="chess-form" onSubmit={save}>
      <div className="chess-form-grid">
        <label>Played on<input type="date" value={f.played_on} onChange={set('played_on')} required /></label>
        <label>Opponent<input value={f.opp_name} onChange={set('opp_name')} required autoFocus={!game} /></label>
        <label>Their rating<input type="number" min="0" max="4000" value={f.opp_rating} onChange={set('opp_rating')} /></label>
        <label>You played
          <select value={f.colour} onChange={set('colour')}><option value="white">White</option><option value="black">Black</option></select></label>
        <label>Result
          <select value={f.result} onChange={set('result')}><option value="win">Won</option><option value="draw">Draw</option><option value="loss">Lost</option></select></label>
        <label>Time control
          <select value={f.time_class} onChange={set('time_class')}>
            {CLASSES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label>Your rating<input type="number" min="0" max="4000" value={f.my_rating} onChange={set('my_rating')} /></label>
        <label>Event<input value={f.event} onChange={set('event')} placeholder="Club night, tournament..." /></label>
        <label>Opening<input value={f.opening} onChange={set('opening')} placeholder="e.g. Sicilian Defense Najdorf" /></label>
      </div>
      <label className="check-row"><input type="checkbox" checked={f.rated} onChange={set('rated')} /> Rated game</label>
      <label className="field">Moves (PGN, optional - to replay it here)
        <textarea rows={3} value={f.pgn} onChange={set('pgn')} placeholder="1. e4 c5 2. Nf3 d6 ..." /></label>
      <div className="button-row">
        <button type="submit" className="primary">{game ? 'Save' : 'Add game'}</button>
        <button type="button" className="plain" onClick={onCancel}>Cancel</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}

// The followed chess.com account and the sync running now (checked every 2 s while it runs; every
// page reloads when it's done).
export function useChessAccount() {
  const { refreshKey, changed } = useApp()
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.chessAccount().then(setAccount).catch((e) => setError(e.message)) }, [refreshKey])
  const running = account?.sync?.running
  useEffect(() => {
    if (!running) return undefined
    const t = setInterval(() => {
      api.chessAccount().then((a) => {
        setAccount(a)
        if (!a.sync.running) changed()
      }).catch(() => {})
    }, 2000)
    return () => clearInterval(t)
  }, [running, changed])
  return { account, setAccount, error }
}

export function ChessSetup({ setAccount }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const connect = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      setAccount(await api.setChessAccount(name))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="card steam-setup" onSubmit={connect}>
      <h2 className="home-card-title">Connect chess.com</h2>
      <p className="muted small">Your games, ratings and puzzles come from chess.com's public data - no password, just your
        username. The first sync reads every month of games (one request each), then it keeps up by itself daily.</p>
      <div className="lookup-row">
        <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="chess.com username or profile link"
          aria-label="chess.com username" />
        <button type="submit" className="primary" disabled={busy || !name.trim()}>{busy ? 'Connecting...' : 'Connect'}</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}

export function ChessSyncBar({ account, setAccount }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const sync = account.sync
  const start = async (full) => {
    setBusy(true)
    setError('')
    try {
      setAccount({ ...account, sync: (await api.syncChess(full)).sync })
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="sync-bar card">
      {account.avatar && <img className="chess-avatar" src={account.avatar} alt="" referrerPolicy="no-referrer" />}
      <span className="grow">
        <strong>{account.title && <span className="pill tint">{account.title}</span>} {account.name || account.username}</strong>
        {sync.running ? (
          <span className="item-meta">{sync.message}{sync.total > 0 && ` (${sync.done} of ${sync.total})`}
            {sync.total > 0 && <span className="fill-bar tint"><span style={{ width: `${(100 * sync.done) / sync.total}%` }} /></span>}</span>
        ) : (
          <span className="item-meta">{account.last_sync_at ? `Synced ${timeAgo(account.last_sync_at)}` : 'Not synced yet'} · syncs by itself once a day</span>
        )}
      </span>
      {!sync.running && (
        <span className="button-row">
          <button type="button" className="primary" onClick={() => start(false)} disabled={busy}>Sync now</button>
          <button type="button" className="plain small" onClick={() => start(true)} disabled={busy}
            title="Read every month of games again">Full sync</button>
        </span>
      )}
      {(error || sync.error || account.last_error) && !sync.running && (
        <p className="alert error small sync-error">{error || sync.error || account.last_error}</p>
      )}
    </div>
  )
}
