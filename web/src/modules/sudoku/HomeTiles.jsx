import { SudokuIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { clockText, useSudokuSummary } from './sudokuParts.js'

// Sudoku's parts of Home (kept apart from its pages): today's daily puzzle and the week's solves.
export function SudokuTiles() {
  const { data: s } = useSudokuSummary()
  if (!s) return <StatSkeleton />
  if (!s.solved && !s.playing_count) return null
  const d = s.daily
  return (
    <>
      <Stat to="/sudoku/today" Icon={SudokuIcon} tone={d?.status === 'solved' ? 'ok' : 'low'} value={d?.status === 'solved' ? clockText(d.seconds) : d ? 'On the go' : 'Waiting'}
        label="Daily sudoku" sub={`streak ${s.daily_streak.current} day${s.daily_streak.current === 1 ? '' : 's'}`} />
      <Stat to="/sudoku/stats" Icon={SudokuIcon} tone="teal" value={s.solved_this_week} label="Sudokus this week" sub={`${s.solved} solved in all`} />
    </>
  )
}
