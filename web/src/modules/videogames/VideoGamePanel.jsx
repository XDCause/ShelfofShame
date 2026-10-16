import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { BellCurveIcon, ClockIcon, HourglassIcon, TrophyIcon } from '../../components/icons.jsx'
import { CompletionBar, GamePicture, playtime, rarity } from './steam.jsx'

// One game - Steam, Epic or Ubisoft, shown the same way: its picture, completion, every achievement
// (unlocked first; locked ones greyed, hidden ones' descriptions kept secret) - split into the main
// game and each DLC when Exophase says which are which - how other players did, links, and Hide.
// Epic / Ubisoft games have ids like "ubisoft-12" (othergames.py): their achievements come from
// Exophase (Epic) or from the game's Steam version, ticked off by you (Ubisoft).
export default function VideoGamePanel({ id, onClose }) {
  const { changed } = useApp()
  const other = typeof id === 'string' && /^(epic|ubisoft)-\d+$/.test(id)
  const otherId = other ? Number(id.split('-')[1]) : null
  const [game, setGame] = useState(null)
  const [error, setError] = useState('')
  const [account, setAccount] = useState(null)
  const [show, setShow] = useState('all')
  useEffect(() => {
    (other ? api.getOtherGame(otherId) : api.getVideoGame(id)).then(setGame).catch((e) => setError(e.message))
    if (!other) api.steamAccount().then(setAccount).catch(() => {})
  }, [id, other, otherId])

  if (!game) return <Drawer title="Game" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const update = (g) => { setGame(g); changed() }
  const hide = async () => update(other ? await api.updateOtherGame(otherId, { hidden: !game.hidden }) : await api.hideVideoGame(id, !game.hidden))
  const remove = async () => {
    await (other ? api.deleteOtherGame(otherId) : api.removeExtraVideoGame(id))
    changed()
    onClose()
  }
  const ubisoft = game.platform === 'ubisoft'
  const onTick = ubisoft ? async (a) => update(await api.tickOtherAchievement(otherId, a.api_name, !a.achieved)) : null
  const groups = dlcGroups(game.achievements)
  const shows = (a) => show === 'all' || (show === 'got' ? a.achieved : !a.achieved)
  const steamId = other ? game.steam_app_id : id
  const removable = other ? !game.source_id : game.extra
  const footer = (
    <>
      {steamId && <a className="button secondary" href={`https://store.steampowered.com/app/${steamId}`} target="_blank" rel="noreferrer">
        {other ? 'Steam store ↗' : 'Store page ↗'}</a>}
      {other && game.page_url && <a className="button plain" href={game.page_url} target="_blank" rel="noreferrer">Exophase ↗</a>}
      {!other && account?.steam_id && game.achievements_total > 0 && (
        <a className="button plain" href={`https://steamcommunity.com/profiles/${account.steam_id}/stats/${id}/achievements`}
          target="_blank" rel="noreferrer">Your achievements on Steam ↗</a>
      )}
      <span className="spacer" />
      {removable
        ? <button type="button" className="plain destructive" onClick={remove}>Remove</button>
        : <button type="button" className="plain" onClick={hide}>{game.hidden ? 'Show on dashboard' : 'Hide'}</button>}
    </>
  )

  return (
    <Drawer title={game.name} onClose={onClose} footer={footer} wide>
      <GamePicture game={game} className="game-header" />
      <section className="panel-section">
        <div className="section-head">
          <strong>{game.achievements_total ? `${game.achievements_done} of ${game.achievements_total} achievements · ${game.percent}%`
            : game.has_achievements === false ? 'This game has no achievements'
              : other ? (!game.source_id && !game.steam_app_id ? 'Hours only - no achievements tracked'
                : ubisoft ? 'No achievement list yet' : 'No achievements read yet') : 'Not read from Steam yet'}</strong>
          {other && <span className={`pill ${ubisoft ? 'teal' : 'purple'}`}>{ubisoft ? 'Ubisoft' : 'Epic'}</span>}
          {game.completed_at && <span className="pill ok">100% · {shortDate(game.completed_at)}</span>}
        </div>
        <CompletionBar game={game} />
        {game.unobtainable_count > 0 && (
          <p className="small muted">{game.unobtainable_count} achievement{game.unobtainable_count === 1 ? " can't" : "s can't"} be
            earned any more (SteamHunters), so {game.unobtainable_count === 1 ? "it isn't" : "they aren't"} counted.</p>
        )}
        {groups.length > 1 && (
          <p className="small dlc-split">
            {groups.map((g) => (
              <span key={g.name}><strong>{g.dlc ? g.name : 'Main game'}</strong> {g.done} of {g.total}{g.done >= g.total && ' ✓'}</span>
            ))}
          </p>
        )}
        {other ? <HoursPlayed game={game} onSaved={update} id={otherId} />
          : game.extra ? <p className="muted small">Added by hand: Steam doesn't list it in your library, so playtime isn't known.</p>
            : <p className="muted small">{game.playtime_minutes > 0 ? `${playtime(game.playtime_minutes)} played` : 'Playtime not known'}
              {game.last_played && ` · last played ${shortDate(game.last_played)}`}</p>}
        {ubisoft && game.challenges_total > 0 && <p className="hint">Ubisoft challenges (from Exophase): {game.challenges_done} of {game.challenges_total}.</p>}
      </section>

      <Compared game={game} />

      {ubisoft && game.achievements.length === 0 && <TypedNumbers game={game} id={otherId} onSaved={update} />}

      {game.achievements.length > 0 && (
        <section className="panel-section">
          <div className="achievement-tools">
            <div className="segmented" role="group" aria-label="Show achievements">
              {[['all', 'All'], ['got', 'Unlocked'], ['left', 'Still to get']].map(([k, label]) => (
                <button key={k} type="button" aria-pressed={show === k} onClick={() => setShow(k)}>{label}</button>
              ))}
            </div>
            {ubisoft && (
              <button type="button" className="plain small" onClick={async () => update(await api.tickAllOther(otherId,
                game.achievements_done < game.achievements_total))}>
                {game.achievements_done < game.achievements_total ? 'Tick all' : 'Untick all'}
              </button>
            )}
          </div>
          {ubisoft && <p className="hint">Tick the ones you have (Ubisoft Connect: the game's Achievements page). The list is the
            game's Steam version's; rarity is Steam players'.</p>}
          {groups.length === 1 ? <AchievementList items={groups[0].items.filter(shows)} onTick={onTick} /> : (
            <div className="dlc-groups">
              {groups.map((g) => {
                const items = g.items.filter(shows)
                const percent = g.total ? Math.round((100 * g.done) / g.total) : 100
                return (
                  <Fold key={g.name} open={!g.dlc} className="dlc-group"
                    title={<>{g.dlc ? g.name : 'Main game'}{g.dlc && <span className="pill purple">DLC</span>}</>}
                    detail={<>{g.done} of {g.total}
                      <span className={percent === 100 ? 'fill-bar ok' : 'fill-bar tint'} aria-hidden="true"><span style={{ width: `${percent}%` }} /></span></>}>
                    {items.length ? <AchievementList items={items} onTick={onTick} /> : <p className="muted small">None here.</p>}
                  </Fold>
                )
              })}
              <p className="hint">Which achievements come with a DLC: Exophase, read when the game's achievements change.</p>
            </div>
          )}
          {other && !ubisoft && <p className="hint">From your Exophase profile; rarity is Exophase players'.</p>}
        </section>
      )}
      {other && <SteamVersion game={game} id={otherId} onSaved={update} />}
      {!other && <JournalMentions kind="videogame" id={game.app_id} name={game.name} onLeave={onClose} />}
    </Drawer>
  )
}

// Epic / Ubisoft: hours played (Exophase doesn't get Epic's, and often not Ubisoft's), saved when you
// leave the box.
function HoursPlayed({ game, id, onSaved }) {
  const [hours, setHours] = useState(game.my_minutes != null ? String(game.my_minutes / 60) : '')
  const save = async () => {
    const value = hours === '' ? null : Number(hours)
    if ((value == null ? null : Math.round(value * 60)) !== game.my_minutes) onSaved(await api.updateOtherGame(id, { hours: value }))
  }
  return (
    <label className="hours-played small muted">Hours played
      <input type="number" min="0" step="0.5" value={hours} placeholder={game.exo_minutes ? String(Math.round(game.exo_minutes / 60)) : ''}
        onChange={(e) => setHours(e.target.value)} onBlur={save} />
      {game.last_played && <span>· last played {shortDate(game.last_played)}</span>}
    </label>
  )
}

// Ubisoft without an achievement list (no Steam version found): the numbers, typed in.
function TypedNumbers({ game, id, onSaved }) {
  const [f, setF] = useState({ done: game.my_done ?? '', total: game.my_total ?? '' })
  const [error, setError] = useState('')
  const num = (v) => (v === '' ? null : Number(v))
  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      onSaved(await api.updateOtherGame(id, { done: num(f.done), total: num(f.total) }))
    } catch (err) {
      setError(err.message)
    }
  }
  return (
    <form className="panel-section" onSubmit={save}>
      <h4 className="section-title">Your achievements</h4>
      <p className="small muted">No Steam version found to list them from, so type the numbers in (or set the Steam version below).</p>
      <div className="other-fields">
        <label>Achievements you have<input type="number" min="0" value={f.done} onChange={(e) => setF({ ...f, done: e.target.value })} /></label>
        <label>Achievements in the game<input type="number" min="0" value={f.total} onChange={(e) => setF({ ...f, total: e.target.value })} /></label>
      </div>
      <button type="submit" className="primary">Save</button>
      {error && <p className="alert error small">{error}</p>}
    </form>
  )
}

// Epic / Ubisoft: the game's Steam version (its picture, SteamHunters' numbers and - for Ubisoft -
// the achievement list come from it), with a way to fix a wrong match.
function SteamVersion({ game, id, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = async (value) => {
    setBusy(true)
    setError('')
    try {
      onSaved(await api.setOtherSteam(id, value))
      setEditing(false)
      setLink('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel-section">
      <p className="small muted">
        {game.steam_app_id ? <>Steam version: app {game.steam_app_id} (picture, other players' numbers
          {game.platform === 'ubisoft' && ' and the achievement list'} come from it). </> : 'No Steam version found. '}
        <button type="button" className="plain small" onClick={() => setEditing(!editing)}>{game.steam_app_id ? 'Not the right game?' : 'Set it'}</button>
      </p>
      {editing && (
        <div className="lookup-row">
          <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://store.steampowered.com/app/..."
            aria-label="Steam store link or app id" />
          <button type="button" className="primary" disabled={busy || !link.trim()} onClick={() => set(link)}>{busy ? 'Reading...' : 'Use it'}</button>
          {game.steam_app_id && <button type="button" className="plain" disabled={busy} onClick={() => set(null)}>Not on Steam</button>}
        </div>
      )}
      {error && <p className="alert error small">{error}</p>}
    </section>
  )
}

// The achievements as groups: the main game first, then each DLC (A to Z), each with how many you have.
function dlcGroups(achievements) {
  const groups = new Map()
  for (const a of achievements) {
    const name = a.dlc ?? ''
    if (!groups.has(name)) groups.set(name, { name: name || 'main', dlc: a.dlc, items: [], done: 0, total: 0 })
    const g = groups.get(name)
    g.items.push(a)
    if (a.achieved) g.done += 1
    if (a.achieved || !a.unobtainable) g.total += 1      // unobtainable ones you don't have don't count
  }
  return [...groups.values()].sort((x, y) => (x.dlc == null ? -1 : y.dlc == null ? 1 : x.name.localeCompare(y.name)))
}

// onTick (Ubisoft): a tick button on each, to mark it as one you have.
export function AchievementList({ items, onTick }) {
  return (
    <ul className="list achievements">
      {items.map((a) => {
        const r = rarity(a.global_percent)
        const secret = a.hidden && !a.achieved
        return (
          <li key={a.api_name} className={a.achieved ? 'achievement got' : 'achievement'}>
            {onTick && (
              <button type="button" className={a.achieved ? 'ach-tick on' : 'ach-tick'} onClick={() => onTick(a)}
                aria-pressed={a.achieved} aria-label={`${a.achieved ? 'Untick' : 'Tick'} ${a.name}`}>{a.achieved ? '✓' : ''}</button>
            )}
            {(a.achieved ? a.icon : a.icon_gray ?? a.icon)
              ? <img className="achievement-icon" src={a.achieved ? a.icon : a.icon_gray ?? a.icon} alt="" loading="lazy" referrerPolicy="no-referrer" />
              : <span className="achievement-icon thumb-empty" />}
            <span className="grow">
              <span className="item-title">{a.name}</span>
              <span className="item-meta">{secret ? 'Hidden achievement' : a.description ?? ''}</span>
              {a.unobtainable && !a.achieved && <span className="item-meta">Can't be earned any more - not counted</span>}
              {a.achieved && a.unlocked_at && <span className="item-meta">Unlocked {shortDate(a.unlocked_at)}</span>}
            </span>
            {a.unobtainable && <span className="pill" title="SteamHunters lists it as unobtainable">Unobtainable</span>}
            {r && <span className={`pill ${r.tone}`} title={r.label ? `${r.label}: ${r.text} of players have it` : `${r.text} of players have it`}>{r.text}</span>}
          </li>
        )
      })}
    </ul>
  )
}

// How you compare, as icon tiles: your time, the median and fastest times to 100%, and how many
// players who started it 100%'d it (SteamHunters); bars to compare the times; Steam's cross-check -
// its rarest achievement's share of all players, the most that can have 100%'d it.
export function Compared({ game: g, hint = "Median, fastest and 100% rate: SteamHunters' players, refreshed with Sync now." }) {
  const hasCommunity = g.sh_median_minutes || g.perfect_rate != null
  if (!hasCommunity && g.rarest_percent == null) return null
  const tiles = [
    ['you', ClockIcon, 'Your time', g.playtime_minutes > 0 ? playtime(g.playtime_minutes) : null, 'tint'],
    ['median', BellCurveIcon, 'Median to 100%', g.sh_median_minutes > 0 ? playtime(g.sh_median_minutes) : null, 'purple'],
    ['fastest', HourglassIcon, 'Fastest 100%', g.sh_fastest_minutes > 0 ? playtime(g.sh_fastest_minutes) : null, 'teal'],
    ['rate', TrophyIcon, '100% rate', g.perfect_rate != null ? `${Number(g.perfect_rate)}%` : null, 'ok'],
  ].filter(([, , , value]) => value)
  const times = [['You', g.playtime_minutes, 'you'], ['Median', g.sh_median_minutes, 'median'], ['Fastest', g.sh_fastest_minutes, 'fastest']]
    .filter(([, minutes]) => minutes)
  const longest = Math.max(1, ...times.map(([, m]) => m))
  return (
    <section className="panel-section compared">
      <h4 className="section-title">Compared with other players</h4>
      {tiles.length > 0 && (
        <div className="compare-tiles">
          {tiles.map(([key, Icon, label, value, tone]) => (
            <div key={key} className="compare-tile">
              <span className={`stat-icon ${tone}`}><Icon size={20} /></span>
              <span><strong>{value}</strong><span className="muted small">{label}</span></span>
            </div>
          ))}
        </div>
      )}
      {g.sh_median_minutes > 0 && times.length > 1 && (
        <ul className="time-bars" aria-label="Playtime compared">
          {times.map(([label, minutes, kind]) => (
            <li key={kind}>
              <span className="time-label">{label}</span>
              <span className="time-track"><span className={`time-fill ${kind}`} style={{ width: `${(100 * minutes) / longest}%` }} /></span>
            </li>
          ))}
        </ul>
      )}
      {g.sh_median_minutes > 0 && g.playtime_minutes > 0 && (
        <p className="small">{g.playtime_minutes <= g.sh_median_minutes
          ? `You've played ${Math.round((100 * g.playtime_minutes) / g.sh_median_minutes)}% of the median time to 100%.`
          : `You've played ${(g.playtime_minutes / g.sh_median_minutes).toFixed(1)}× the median time to 100%.`}
          {g.perfect_rate != null && ` ${g.sh_players_perfected.toLocaleString()} of ${g.sh_players_started.toLocaleString()} players who started it have 100%'d it`}
          {g.sh_points ? ` · ${g.sh_points.toLocaleString()} points.` : '.'}</p>
      )}
      {g.rarest_percent != null && (
        <p className="small muted">Steam's cross-check: its rarest achievement is held by {Number(g.rarest_percent)}% of all
          players, so no more than that have 100%'d it.</p>
      )}
      {hasCommunity && <p className="hint">{hint}</p>}
      {!hasCommunity && g.achievements_done > 0 && <p className="hint">SteamHunters has no numbers for this game (yet).</p>}
    </section>
  )
}
