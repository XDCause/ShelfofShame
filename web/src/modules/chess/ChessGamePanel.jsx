import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import Board from './Board.jsx'
import { OtbForm, RatingChange, ResultPill, timeControl } from './chessParts.jsx'

// One game: how it went (result, ratings, accuracy, opening), the moves on a board, your notes,
// journal pages about it. Over-the-board games can be changed or removed; online ones come from
// chess.com (only their notes are yours to change).
export default function ChessGamePanel({ id, onClose }) {
  const { changed } = useApp()
  const [game, setGame] = useState(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [notes, setNotes] = useState('')
  const [saved, setSaved] = useState('')
  useEffect(() => {
    api.chessGame(id).then((g) => { setGame(g); setNotes(g.notes ?? '') }).catch((e) => setError(e.message))
  }, [id])
  if (!game) return <Drawer title="Game" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const otb = game.source === 'otb'
  const saveNotes = async () => {
    if ((game.notes ?? '') === notes) return
    const g = await api.updateChessGame(id, { notes })
    setGame(g)
    setSaved('Saved ✓')
    changed()
  }
  const remove = async () => {
    await api.deleteChessGame(id)
    changed()
    onClose()
  }
  const footer = (
    <>
      {game.url && <a className="button secondary" href={game.url} target="_blank" rel="noreferrer">On chess.com ↗</a>}
      <span className="spacer" />
      {otb && !editing && <button type="button" className="plain" onClick={() => setEditing(true)}>Edit details</button>}
      {otb && <button type="button" className="plain destructive" onClick={remove}>Remove</button>}
    </>
  )
  return (
    <Drawer title={`vs ${game.opp_name}`} onClose={onClose} footer={footer} wide>
      <section className="panel-section">
        <div className="section-head">
          <strong><ResultPill game={game} /> {game.colour === 'white' ? 'White' : 'Black'} · {shortDate(game.played_at)}</strong>
          <span className={`pill ${otb ? 'teal' : 'tint'}`}>{otb ? 'Over the board' : 'chess.com'}</span>
        </div>
        <dl className="chess-facts">
          <dt>Time</dt><dd>{game.time_class[0].toUpperCase() + game.time_class.slice(1)}
            {game.time_control && ` · ${timeControl(game.time_control)}`}{!game.rated && ' · unrated'}{game.rules !== 'chess' && ` · ${game.rules}`}</dd>
          {(game.my_rating || game.opp_rating) && (
            <><dt>Ratings</dt><dd>You {game.my_rating ?? '?'} <RatingChange value={game.rating_change} /> · {game.opp_name} {game.opp_rating ?? '?'}</dd></>
          )}
          {game.accuracy != null && <><dt>Accuracy</dt><dd>You {Number(game.accuracy).toFixed(1)}% · {game.opp_name} {Number(game.opp_accuracy).toFixed(1)}%</dd></>}
          {game.opening && <><dt>Opening</dt><dd>{game.opening}{game.eco && <span className="muted"> ({game.eco})</span>}</dd></>}
          {game.moves != null && <><dt>Length</dt><dd>{game.moves} moves</dd></>}
          {game.event && <><dt>Event</dt><dd>{game.event}</dd></>}
        </dl>
      </section>

      {editing && (
        <section className="panel-section">
          <OtbForm game={game} onSaved={(g) => { setGame(g); setEditing(false); changed() }} onCancel={() => setEditing(false)} />
        </section>
      )}

      {game.pgn ? <section className="panel-section"><Board pgn={game.pgn} colour={game.colour} /></section>
        : otb && <p className="panel-section small muted">No moves saved. Edit details to paste them (PGN) and replay the game here.</p>}

      <section className="panel-section">
        <label className="field">Notes
          <textarea rows={3} value={notes} onChange={(e) => { setNotes(e.target.value); setSaved('') }} onBlur={saveNotes}
            placeholder="What happened, what to remember..." />
        </label>
        {saved && <span className="muted small">{saved}</span>}
      </section>
      <JournalMentions kind="chess" id={game.game_id} name={`chess vs ${game.opp_name}`} onLeave={onClose} />
    </Drawer>
  )
}
