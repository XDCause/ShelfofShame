import { api } from '../../api.js'
import { ChessIcon, TrophyIcon } from '../../components/icons.jsx'
import { useApp } from '../../core/app-context.js'
import Stat, { Change, StatSkeleton } from '../../core/Stat.jsx'
import { useShared } from '../../core/useShared.js'
import { className } from './chessParts.jsx'

// chess's parts of Home (ChessTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
export const useChessSummary = () => {
  const { refreshKey } = useApp()
  return useShared(`chess-summary-${refreshKey}`, () => api.chessSummary())
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
      {s.puzzles?.highest && <Stat to="/chess/dashboard" Icon={TrophyIcon} tone="ok" value={s.puzzles.highest} label="Puzzles (best)"
        sub={s.puzzles.rush_best ? `Puzzle Rush best ${s.puzzles.rush_best}` : 'chess.com puzzles'} />}
    </>
  )
}
