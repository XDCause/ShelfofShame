import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { UsersIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { firstPlayerText, streakText } from './statsHelpers.js'
import { minutesText, scoreText } from './tableParts.jsx'

const pct = (a, b) => (b ? `${Math.round((100 * a) / b)}%` : '–')

// The people you play with (api/app/boardgames_people.py): how each of you does, you against each of them (your
// nemesis, who you beat most, your best co-op partner), your groups, every game's times and records, where you play.
// Tap a player to rename them, say "this is me", merge a duplicate or remove someone in no plays.
export function PlayersView() {
  const { refreshKey, changed } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(null)        // the player being edited
  useEffect(() => {
    Promise.all([api.boardGameStats(), api.boardGamePlayers()]).then(([stats, roster]) => setData({ stats, roster }))
      .catch((e) => setError(e.message))
  }, [refreshKey])
  if (error && !data) return <p className="alert error">{error}</p>
  if (!data) return <p className="muted loading">Loading...</p>
  const { stats, roster } = data
  const players = stats.players
  const me = players.find((p) => p.is_me)
  const others = players.filter((p) => !p.is_me && p.vs_me?.together)
  const most = (key, min = 2) => others.filter((p) => p.vs_me[key] > 0 && p.vs_me.together >= min)
    .sort((a, b) => b.vs_me[key] - a.vs_me[key] || a.vs_me.together - b.vs_me.together)[0]
  const nemesis = most('they_beat')
  const easiest = most('i_beat')
  const partner = others.filter((p) => p.vs_me.coop_plays > 0)
    .sort((a, b) => b.vs_me.coop_wins / b.vs_me.coop_plays - a.vs_me.coop_wins / a.vs_me.coop_plays || b.vs_me.coop_plays - a.vs_me.coop_plays)[0]
  const run = async (fn) => {
    setError('')
    try { await fn(); changed() } catch (e) { setError(e.message) }
  }

  if (!players.length) {
    return (
      <section className="page">
        <EmptyState Icon={UsersIcon} title="No players yet">
          Start a play or log one, and everyone you play with is kept here: their wins, how you do against them, and your
          groups for next time.</EmptyState>
      </section>
    )
  }
  return (
    <section className="page">
      {error && <p className="alert error" role="alert">{error}</p>}
      <div className="stat-grid card">
        <div><span>Players</span><strong>{players.length}</strong>
          <small className="muted">{roster.groups.length ? `${roster.groups.length} group${roster.groups.length === 1 ? '' : 's'}` : 'no groups yet'}</small></div>
        <div><span>Your win rate</span><strong>{me ? pct(me.wins, me.contests) : '–'}</strong>
          {me && <small className="muted">{me.wins} of {me.contests} games with a winner</small>}</div>
        <div><span>Teaching</span><strong>{minutesText(stats.times.teach) ?? '0 min'}</strong>
          <small className="muted">{minutesText(stats.times.playing) ?? '0 min'} playing</small></div>
      </div>

      {!me && (
        <div className="card bgt-whoami">
          <p><strong>Which one is you?</strong> Pick yourself and the stats can say how you do against everyone.</p>
          <select aria-label="Which player is you" defaultValue="" onChange={(e) => e.target.value
            && run(() => api.updateBoardGamePlayer(Number(e.target.value), { is_me: true }))}>
            <option value="">Choose...</option>
            {players.map((p) => <option key={p.player_id} value={p.player_id}>{p.name}</option>)}
          </select>
        </div>
      )}

      {me && (nemesis || easiest || partner) && (
        <div className="bgt-rivals">
          {nemesis && <div className="card bgt-rival"><span className="bgt-rival-label">Nemesis</span><strong>{nemesis.name}</strong>
            <span className="muted small">beat you {nemesis.vs_me.they_beat} of {nemesis.vs_me.together} times</span></div>}
          {easiest && <div className="card bgt-rival"><span className="bgt-rival-label">You have the edge on</span><strong>{easiest.name}</strong>
            <span className="muted small">you beat them {easiest.vs_me.i_beat} of {easiest.vs_me.together} times</span></div>}
          {partner && <div className="card bgt-rival"><span className="bgt-rival-label">Best co-op partner</span><strong>{partner.name}</strong>
            <span className="muted small">won {partner.vs_me.coop_wins} of {partner.vs_me.coop_plays} together</span></div>}
        </div>
      )}

      <div className="bgt-rivals">
        <div className="card bgt-rival"><span className="bgt-rival-label">Your H-index</span><strong>{stats.h_index.n}</strong>
          {stats.h_index.n > 0 && <span className="muted small">{stats.h_index.n} game{stats.h_index.n === 1 ? ' has' : 's have'} each been played at least {stats.h_index.n} time{stats.h_index.n === 1 ? '' : 's'}
            {stats.h_index.games.length > 0 && `: ${stats.h_index.games.map((g) => `${g.name} (${g.plays})`).join(', ')}`}</span>}
          <span className="muted small">{stats.h_index.plays_to_next} more play{stats.h_index.plays_to_next === 1 ? '' : 's'} to reach {stats.h_index.next_n}</span></div>
        {me && <div className="card bgt-rival"><span className="bgt-rival-label">Your win streak</span><strong>{streakText(me.streak.current)}</strong>
          <span className="muted small">longest {me.streak.longest} (finished games with a winner, co-op left out)</span></div>}
        {stats.first_player.plays > 0 && <div className="card bgt-rival"><span className="bgt-rival-label">Going first</span>
          <strong>{stats.first_player.rate}% win</strong><span className="muted small">{firstPlayerText(stats.first_player)}</span></div>}
      </div>
      {stats.first_player.games.length > 0 && (
        <details className="fold bgs-first">
          <summary><span className="fold-title">Does going first help?</span><span className="fold-detail">per game, 3 or more plays</span></summary>
          <div className="fold-body"><ul className="list compact">
            {stats.first_player.games.map((g) => (
              <li key={g.game_id} className="bgt-place"><span className="grow">{g.name}</span>
                <span className="muted small">first player won {g.wins} of {g.plays} ({g.rate}%) · chance {g.chance}%</span></li>
            ))}
          </ul></div>
        </details>
      )}

      <h3 className="section-title">Everyone</h3>
      <ul className="list">
        {players.map((p) => (
          <li key={p.player_id}>
            <button type="button" className="row-button" aria-expanded={open === p.player_id} onClick={() => setOpen(open === p.player_id ? null : p.player_id)}>
              <span className="thumb thumb-icon purple bgt-initial" aria-hidden="true">{p.name.slice(0, 1).toUpperCase()}</span>
              <span className="grow">
                <span className="item-title">{p.name}{p.is_me && <span className="pill">You</span>}</span>
                <span className="item-meta">{[`${p.plays} play${p.plays === 1 ? '' : 's'}`, p.contests ? `${p.wins} win${p.wins === 1 ? '' : 's'} (${pct(p.wins, p.contests)})` : null,
                  `${p.games} game${p.games === 1 ? '' : 's'}`, p.streak?.longest > 1 && `best streak ${p.streak.longest}${p.streak.current > 1 ? `, now ${p.streak.current}` : ''}`,
                  p.last_played && `last ${shortDate(p.last_played)}`].filter(Boolean).join(' · ')}</span>
              </span>
              {p.vs_me?.together > 0 && <span className="pill" title="You against them (games one of you placed higher)">
                You {p.vs_me.i_beat}–{p.vs_me.they_beat}</span>}
            </button>
            {open === p.player_id && <PlayerEdit player={p} players={players} run={run} onDone={() => setOpen(null)} />}
          </li>
        ))}
      </ul>

      <Groups roster={roster} run={run} />

      {stats.games.length > 0 && (
        <>
          <h3 className="section-title">Games</h3>
          <div className="table-wrap card" tabIndex={0} role="region" aria-label="Games with this group (scrolls sideways)">
            <table className="bgt-table">
              <thead><tr><th>Game</th><th>Plays</th><th>Teach</th><th>Play</th>{me && <th>Your wins</th>}{me && <th>Your best</th>}<th>Record</th><th>Fun</th></tr></thead>
              <tbody>
                {stats.games.map((g) => (
                  <tr key={g.game_id}>
                    <th scope="row">{g.name}</th>
                    <td>{g.plays}</td>
                    <td>{minutesText(g.avg_teach) ?? '–'}</td>
                    <td>{minutesText(g.avg_minutes) ?? '–'}</td>
                    {me && <td>{g.scoring === 'coop' ? `${g.my_wins} of ${g.my_plays}` : g.my_plays ? `${g.my_wins} of ${g.my_plays}` : '–'}</td>}
                    {me && <td>{g.my_best != null ? scoreText(g.my_best) : '–'}</td>}
                    <td>{g.record ? `${scoreText(g.record.score)} · ${g.record.name}` : '–'}</td>
                    <td>{g.avg_fun != null ? `★ ${Number(g.avg_fun)}` : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {stats.places.length > 0 && (
        <>
          <h3 className="section-title">Where you play</h3>
          <ul className="list compact">
            {stats.places.map((pl) => (
              <li key={pl.location} className="bgt-place"><span className="grow">{pl.location}</span>
                <span className="muted small">{pl.plays} play{pl.plays === 1 ? '' : 's'} · last {shortDate(pl.last_played)}</span></li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function PlayerEdit({ player, players, run, onDone }) {
  const [name, setName] = useState(player.name)
  const [into, setInto] = useState('')
  return (
    <div className="inline-form bgt-player-edit">
      <div className="bgt-new">
        <input value={name} onChange={(e) => setName(e.target.value)} aria-label={`Rename ${player.name}`} maxLength={80} />
        <button type="button" className="secondary" disabled={!name.trim() || name.trim() === player.name}
          onClick={() => run(async () => { await api.updateBoardGamePlayer(player.player_id, { name }); onDone() })}>Rename</button>
      </div>
      {!player.is_me && <button type="button" className="plain small"
        onClick={() => run(() => api.updateBoardGamePlayer(player.player_id, { is_me: true }))}>This is me</button>}
      {players.length > 1 && (
        <div className="bgt-new">
          <select value={into} onChange={(e) => setInto(e.target.value)} aria-label={`Merge ${player.name} into`}>
            <option value="">Same person as...</option>
            {players.filter((p) => p.player_id !== player.player_id).map((p) => <option key={p.player_id} value={p.player_id}>{p.name}</option>)}
          </select>
          <button type="button" className="secondary" disabled={!into}
            onClick={() => run(async () => { await api.mergeBoardGamePlayer(player.player_id, Number(into)); onDone() })}>Merge</button>
        </div>
      )}
      {player.plays === 0 && <button type="button" className="plain small destructive"
        onClick={() => run(async () => { await api.deleteBoardGamePlayer(player.player_id); onDone() })}>Remove {player.name}</button>}
    </div>
  )
}

// Your usual groups: added to a play in one tap.
function Groups({ roster, run }) {
  const [editing, setEditing] = useState(null)   // a group, or {} for a new one
  const byId = Object.fromEntries(roster.players.map((p) => [p.player_id, p]))
  return (
    <>
      <div className="section-head">
        <h3 className="section-title">Groups</h3>
        {!editing && <button type="button" className="secondary small" onClick={() => setEditing({ name: '', player_ids: [] })}>+ New group</button>}
      </div>
      {roster.groups.length === 0 && !editing && <p className="muted small">A group (your Thursday crew, family) adds everyone in it to a play in one tap.</p>}
      <ul className="list compact">
        {roster.groups.map((g) => (
          <li key={g.group_id} className="bgt-group-row">
            <span className="grow">
              <span className="item-title">{g.name}</span>
              <span className="item-meta">{g.player_ids.map((i) => byId[i]?.name).filter(Boolean).join(', ') || 'nobody yet'}</span>
            </span>
            <button type="button" className="plain small" onClick={() => setEditing(g)}>Edit</button>
          </li>
        ))}
      </ul>
      {editing && <GroupForm group={editing} players={roster.players} run={run} onDone={() => setEditing(null)} />}
    </>
  )
}

function GroupForm({ group, players, run, onDone }) {
  const [name, setName] = useState(group.name)
  const [ids, setIds] = useState(group.player_ids)
  const save = () => run(async () => {
    if (group.group_id) await api.updatePlayerGroup(group.group_id, { name, player_ids: ids })
    else await api.addPlayerGroup({ name, player_ids: ids })
    onDone()
  })
  return (
    <div className="inline-form card">
      <label className="field wide"><span className="field-label">Group name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Thursday crew" maxLength={60} /></label>
      <div className="chips" role="group" aria-label="Who's in it">
        {players.map((p) => (
          <button key={p.player_id} type="button" className="chip-filter" aria-pressed={ids.includes(p.player_id)}
            onClick={() => setIds(ids.includes(p.player_id) ? ids.filter((x) => x !== p.player_id) : [...ids, p.player_id])}>{p.name}</button>
        ))}
      </div>
      <div className="button-row">
        <button type="button" className="primary" onClick={save} disabled={!name.trim()}>Save group</button>
        <button type="button" className="plain" onClick={onDone}>Cancel</button>
        {group.group_id && <button type="button" className="plain destructive"
          onClick={() => run(async () => { await api.deletePlayerGroup(group.group_id); onDone() })}>Delete group</button>}
      </div>
    </div>
  )
}
