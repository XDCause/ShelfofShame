import { BookIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { useReadingSummary } from './readingParts.jsx'

// reading's parts of Home (ReadingTiles): kept apart from its pages so Home doesn't load them
// (each hobby's pages load only when you open it - health check, 2026-10-21).
// Home: books this year (against the goal) and the book you're reading.
export function ReadingTiles() {
  const { data: s } = useReadingSummary()
  if (!s) return <StatSkeleton />
  if (Object.values(s.counts).every((n) => n === 0)) return null
  const now = s.reading[0]
  return (
    <>
      <Stat to="/reading/dashboard" Icon={BookIcon} tone="ok" value={s.goal.goal ? `${s.year.books}/${s.goal.goal}` : s.year.books}
        label={`Books in ${s.goal.year}`}
        sub={s.goal.goal ? (s.goal.reached ? 'goal reached' : s.goal.ahead_by >= 0 ? 'on pace' : `${Math.ceil(-s.goal.ahead_by)} behind pace`) : 'finished this year'} />
      {now && <Stat to="/reading/dashboard" Icon={BookIcon} tone="tint" value={now.percent != null ? `${now.percent}%` : 'Reading'}
        label={now.title} sub={now.current_page != null ? `p. ${now.current_page}${now.pages ? ` of ${now.pages}` : ''}` : now.author ?? ''} />}
    </>
  )
}
