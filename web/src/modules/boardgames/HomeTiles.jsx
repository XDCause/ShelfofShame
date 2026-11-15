import { api } from '../../api.js'
import { DiceIcon, TimerIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'

// boardgames's parts of Home (BoardGamesTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
// Home: two tiles (just the summary - not every game).
export function BoardGamesTiles() {
  const { refreshKey } = useApp()
  const { data: summary } = useShared(`boardgames-summary-${refreshKey}`, api.boardGameSummary)
  if (!summary) return <><StatSkeleton /><StatSkeleton /></>
  const live = summary.live?.[0]
  return (
    <>
      {live && <Stat to="/boardgames/games" Icon={TimerIcon} tone="teal" value={live.game_name} label="Playing now"
        sub={`since ${new Date(live.started_at).toLocaleTimeString('en-AU', { hour: 'numeric', minute: '2-digit' })}`} />}
      <Stat to="/boardgames/games" Icon={DiceIcon} tone="purple" value={summary.owned} label="Board games"
        sub={summary.wanted ? `${summary.wanted} wanted` : 'on the shelf'} />
      <Stat to="/boardgames/plays" Icon={TrophyIcon} tone="teal" value={summary.plays_this_month} label="Plays"
        sub="this month" />
    </>
  )
}
