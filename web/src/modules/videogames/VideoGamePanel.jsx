import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Drawer from '../../components/Drawer.jsx'
import Fold from '../../components/Fold.jsx'
import { useApp } from '../../core/app-context.js'
import JournalMentions from '../../core/journal/JournalMentions.jsx'
import { BellCurveIcon, ClockIcon, HourglassIcon, TrophyIcon } from '../../components/icons.jsx'
import { CompletionBar, GamePicture, playtime, rarity } from './steam.jsx'

// One game: its picture, completion, every achievement (unlocked first; locked ones greyed, hidden
// ones' descriptions kept secret) - split into the main game and each DLC when Exophase says which
// are which - links to Steam, journal pages about it, and Hide.
export default function VideoGamePanel({ id, onClose }) {
  const { changed } = useApp()
  const [game, setGame] = useState(null)
  const [error, setError] = useState('')
  const [account, setAccount] = useState(null)
  const [show, setShow] = useState('all')
  useEffect(() => {
    api.getVideoGame(id).then(setGame).catch((e) => setError(e.message))
    api.steamAccount().then(setAccount).catch(() => {})
  }, [id])

  if (!game) return <Drawer title="Game" onClose={onClose}>{error ? <p className="alert error">{error}</p> : <p className="muted">Loading...</p>}</Drawer>

  const hide = async () => {
    setGame(await api.hideVideoGame(id, !game.hidden))
    changed()
  }
  const remove = async () => {
    await api.removeExtraVideoGame(id)
    changed()
    onClose()
  }
  const groups = dlcGroups(game.achievements)
  const shows = (a) => show === 'all' || (show === 'got' ? a.achieved : !a.achieved)
  const footer = (
    <>
      <a className="button secondary" href={`https://store.steampowered.com/app/${id}`} target="_blank" rel="noreferrer">Store page ↗</a>
      {account?.steam_id && game.achievements_total > 0 && (
        <a className="button plain" href={`https://steamcommunity.com/profiles/${account.steam_id}/stats/${id}/achievements`}
          target="_blank" rel="noreferrer">Your achievements on Steam ↗</a>
      )}
      <span className="spacer" />
      {game.extra
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
            : game.has_achievements === false ? 'This game has no achievements' : 'Not read from Steam yet'}</strong>
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
        {game.extra
          ? <p className="muted small">Added by hand: Steam doesn't list it in your library, so playtime isn't known.</p>
          : <p className="muted small">{playtime(game.playtime_minutes)} played{game.last_played && ` · last played ${shortDate(game.last_played)}`}</p>}
      </section>

      <Compared game={game} />

      {game.achievements.length > 0 && (
        <section className="panel-section">
          <div className="segmented" role="group" aria-label="Show achievements">
            {[['all', 'All'], ['got', 'Unlocked'], ['left', 'Still to get']].map(([k, label]) => (
              <button key={k} type="button" aria-pressed={show === k} onClick={() => setShow(k)}>{label}</button>
            ))}
          </div>
          {groups.length === 1 ? <AchievementList items={groups[0].items.filter(shows)} /> : (
            <div className="dlc-groups">
              {groups.map((g) => {
                const items = g.items.filter(shows)
                const percent = g.total ? Math.round((100 * g.done) / g.total) : 100
                return (
                  <Fold key={g.name} open={!g.dlc} className="dlc-group"
                    title={<>{g.dlc ? g.name : 'Main game'}{g.dlc && <span className="pill purple">DLC</span>}</>}
                    detail={<>{g.done} of {g.total}
                      <span className={percent === 100 ? 'fill-bar ok' : 'fill-bar tint'} aria-hidden="true"><span style={{ width: `${percent}%` }} /></span></>}>
                    {items.length ? <AchievementList items={items} /> : <p className="muted small">None here.</p>}
                  </Fold>
                )
              })}
              <p className="hint">Which achievements come with a DLC: Exophase, read when the game's achievements change.</p>
            </div>
          )}
        </section>
      )}
      <JournalMentions kind="videogame" id={game.app_id} name={game.name} onLeave={onClose} />
    </Drawer>
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

function AchievementList({ items }) {
  return (
    <ul className="list achievements">
      {items.map((a) => {
        const r = rarity(a.global_percent)
        const secret = a.hidden && !a.achieved
        return (
          <li key={a.api_name} className={a.achieved ? 'achievement got' : 'achievement'}>
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
function Compared({ game: g }) {
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
      {hasCommunity && <p className="hint">Median, fastest and 100% rate: SteamHunters' players, refreshed with Sync now.</p>}
      {!hasCommunity && g.achievements_done > 0 && <p className="hint">SteamHunters has no numbers for this game (yet).</p>}
    </section>
  )
}
