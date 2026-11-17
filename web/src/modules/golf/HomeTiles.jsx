import { shortDate } from '../../api.js'
import { GolfIcon, TrophyIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { hcpText, plural, toPar } from './golfFormat.js'
import { useGolfSummary } from './golfParts.jsx'

// Golf's part of Home (GolfTiles): the handicap and the last round - kept apart from its pages so Home doesn't load
// them. Nothing until the first round is finished.
export function GolfTiles() {
  const { data: s } = useGolfSummary()
  if (!s) return <StatSkeleton />
  if (!s.rounds) return null
  const h = s.handicap
  const last = s.recent[0]
  const lastValue = !last ? '—' : last.format === 'Stableford' || last.gross == null ? `${last.points} pts` : last.gross
  return (
    <>
      <Stat to="/golf/dashboard" Icon={TrophyIcon} tone="ok" value={hcpText(h.current)}
        label={h.source === 'official' ? 'GA Handicap' : 'Handicap (estimate)'}
        sub={`${plural(s.this_year.rounds, 'round')} in ${s.year}`} />
      {last && (
        <Stat to="/golf/rounds" Icon={GolfIcon} tone="teal" value={lastValue} label="Last round"
          sub={[last.course_name, last.gross != null && last.format === 'Stableford' ? `${last.gross} (${toPar(last.to_par)})` : null,
            shortDate(last.played_on)].filter(Boolean).join(' · ')} />
      )}
    </>
  )
}
