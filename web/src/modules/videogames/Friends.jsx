import { useCallback, useEffect, useState } from 'react'
import { api, timeAgo } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import { UsersIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import EmptyState from '../../core/EmptyState.jsx'
import { GamePicture, playtime } from './steam.jsx'

// Friends (api/app/vgfriends.py): your Steam friends - from your friends list when it's public,
// or added by their profile - what they're playing, and (Compare) how they're doing on the games
// you both have with achievements.

function Avatar({ friend, size = 48 }) {
  return friend.avatar_url
    ? <img className="friend-avatar" src={friend.avatar_url} alt="" width={size} height={size} referrerPolicy="no-referrer" />
    : <span className="friend-avatar empty" style={{ width: size, height: size }} aria-hidden="true">{(friend.name ?? '?')[0]}</span>
}

function Status({ friend }) {
  if (friend.playing) return <span className="pill ok">Playing {friend.playing}</span>
  if (!friend.public) return <span className="pill">Private profile</span>
  return <span className={friend.status && friend.status !== 'Offline' ? 'pill tint' : 'pill'}>{friend.status ?? 'Offline'}</span>
}

export function FriendsView() {
  const { refreshKey, openPanel } = useApp()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  useEffect(() => {
    api.videoGameFriends().then((d) => {
      setData(d)
      api.refreshFriends().then(setData).catch((e) => setError(e.message))   // names and status, at most every 10 minutes
    }).catch((e) => setError(e.message))
  }, [refreshKey])
  if (!data) return error ? <p className="alert error">{error}</p> : <p className="muted loading">Loading...</p>
  const friends = data.friends

  return (
    <section className="page">
      <div className="toolbar">
        <p className="summary grow"><strong>{friends.length}</strong> friend{friends.length === 1 ? '' : 's'}
          {friends.some((f) => f.playing) && <span className="muted"> · {friends.filter((f) => f.playing).length} playing now</span>}</p>
        <button type="button" className="primary" onClick={() => setAdding(!adding)}>+ Add a friend</button>
      </div>
      {data.list_public === false && (
        <p className="alert low small">Your Steam friends list is private, so it can't be read. To see everyone, set <strong>Friends
          List</strong> to Public in Steam (Profile → Edit Profile → Privacy Settings) - or add friends here by their profile.</p>
      )}
      {error && <p className="alert error small">{error}</p>}
      {adding && <AddFriend onAdded={(f) => { setAdding(false); openPanel('vgfriend', { id: f.steam_id }) }} />}
      {friends.length === 0 ? (
        <EmptyState Icon={UsersIcon} title="No friends here yet" action="+ Add a friend" onAction={() => setAdding(true)}>
          Add a friend by their Steam profile link or name, then compare how you're both doing on the games you share.</EmptyState>
      ) : (
        <ul className="friend-grid">
          {friends.map((f) => (
            <li key={f.steam_id}>
              <button type="button" className="friend-card card" onClick={() => openPanel('vgfriend', { id: f.steam_id })}>
                <Avatar friend={f} />
                <span className="grow">
                  <span className="item-title">{f.name ?? 'Steam user'}</span>
                  <Status friend={f} />
                  <span className="item-meta">{f.comparing ? `Comparing... ${f.comparing.done} of ${f.comparing.total || '?'}`
                    : f.compared_at ? (f.compare_error ? "Couldn't compare" : `${f.common} games in common · you lead ${f.you_ahead}, they lead ${f.they_ahead}`)
                      : f.public ? 'Not compared yet' : ''}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {data.hidden > 0 && <p className="hint">{data.hidden} hidden.</p>}
    </section>
  )
}

function AddFriend({ onAdded }) {
  const { changed } = useApp()
  const [profile, setProfile] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const add = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const f = await api.addFriend(profile)
      changed()
      onAdded(f)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return (
    <form className="card add-friend" onSubmit={add}>
      <p className="small muted">Their Steam profile link (steamcommunity.com/id/... or /profiles/...) or the name in it.</p>
      <div className="lookup-row">
        <input value={profile} onChange={(e) => setProfile(e.target.value)} required autoFocus aria-label="Friend's Steam profile"
          placeholder="https://steamcommunity.com/id/..." />
        <button type="submit" className="primary" disabled={busy || profile.trim().length < 2}>{busy ? 'Finding...' : 'Add'}</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}

// One friend: status, Compare, and the games you share - your progress and theirs.
export function FriendPanel({ id, onClose }) {
  const { changed } = useApp()
  const [friend, setFriend] = useState(null)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)
  const load = useCallback(() => api.videoGameFriend(id).then(setFriend).catch((e) => setError(e.message)), [id])
  useEffect(() => { load() }, [load])
  useEffect(() => {                                   // while comparing, look again every 2 seconds
    if (!friend?.comparing) return undefined
    const timer = setInterval(() => api.videoGameFriend(id).then((f) => { setFriend(f); if (!f.comparing) changed() }).catch(() => {}), 2000)
    return () => clearInterval(timer)
  }, [friend?.comparing, id, changed])
  if (!friend) return <Drawer title="Friend" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const compare = async () => { setError(''); try { setFriend(await api.compareFriend(id)) } catch (e) { setError(e.message) } }
  const remove = async () => { await api.removeFriend(id); changed(); onClose() }
  const footer = confirm ? (
    <span className="confirm">{friend.from_list ? 'Hide' : 'Remove'} {friend.name}?
      <button type="button" className="danger" onClick={remove}>{friend.from_list ? 'Hide' : 'Remove'}</button>
      <button type="button" className="plain" onClick={() => setConfirm(false)}>Cancel</button>
    </span>
  ) : (
    <>
      {friend.profile_url && <a className="button secondary" href={friend.profile_url} target="_blank" rel="noreferrer">Steam profile ↗</a>}
      <span className="spacer" />
      <button type="button" className="plain destructive" onClick={() => setConfirm(true)}>{friend.from_list ? 'Hide' : 'Remove'}</button>
    </>
  )
  const games = friend.games
  return (
    <Drawer title={friend.name ?? 'Friend'} onClose={onClose} footer={footer} wide>
      <section className="panel-section friend-head">
        <Avatar friend={friend} size={64} />
        <span className="grow">
          <span className="item-title">{friend.name}</span>
          <Status friend={friend} />
          {friend.games_owned != null && <span className="item-meta">{friend.games_owned} games on Steam</span>}
        </span>
        {friend.public && (
          <button type="button" className="primary" onClick={compare} disabled={Boolean(friend.comparing)}>
            {friend.comparing ? `Comparing ${friend.comparing.done} of ${friend.comparing.total || '?'}...` : friend.compared_at ? 'Compare again' : 'Compare'}</button>
        )}
      </section>
      {error && <p className="alert error small">{error}</p>}
      {!friend.public && <p className="alert low small">Their profile is private, so only their name can be shown.</p>}
      {friend.compare_error && <p className="alert error small">{friend.compare_error}</p>}
      {friend.compared_at && !friend.compare_error && (
        <section className="panel-section">
          <div className="stat-grid">
            <div><span>Games in common</span><strong>{friend.common}</strong></div>
            <div><span>You're ahead</span><strong>{friend.you_ahead}</strong></div>
            <div><span>They're ahead</span><strong>{friend.they_ahead}</strong></div>
            <div><span>Their 100%s here</span><strong>{friend.their_perfect}</strong></div>
          </div>
          <p className="hint">Games you both have with achievements · compared {timeAgo(friend.compared_at)}.</p>
          <ul className="list friend-games">
            {games.map((g) => (
              <li key={g.app_id}>
                <GamePicture game={g} className="friend-game-pic" />
                <span className="grow">
                  <span className="item-title">{g.name}</span>
                  <span className="vs-row"><span className="vs-who">You</span>
                    <span className="fill-bar tint"><span style={{ width: `${g.my_percent ?? 0}%` }} /></span>
                    <span className="vs-num">{g.my_done}/{g.my_total}</span></span>
                  <span className="vs-row"><span className="vs-who">{friend.name}</span>
                    <span className="fill-bar purple"><span style={{ width: `${g.their_percent ?? 0}%` }} /></span>
                    <span className="vs-num">{g.their_total ? `${g.their_done}/${g.their_total}` : 'hidden'}</span></span>
                  {g.their_minutes > 0 && <span className="item-meta">They've played {playtime(g.their_minutes)}{g.my_minutes > 0 && ` · you ${playtime(g.my_minutes)}`}</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!friend.compared_at && friend.public && !friend.comparing && (
        <p className="panel-section muted small">Compare reads their games list and their achievements in each game you both have
          (their Game details must be public). It takes a moment for a big library.</p>
      )}
    </Drawer>
  )
}
