import { LanguageIcon, TrophyIcon } from '../../components/icons.jsx'
import Stat, { StatSkeleton } from '../../core/Stat.jsx'
import { minutesText, plural } from './answers.js'
import { useLanguageSummary } from './langParts.js'

// Language learning's parts of Home (kept apart from its pages): cards to review today, and this week's study against
// your daily goals. Both show once you've added a language.
export function LanguageTiles() {
  const { data: s } = useLanguageSummary()
  if (!s) return <StatSkeleton />
  if (!s.languages.length) return null
  const toDo = s.due + s.new
  return (
    <>
      <Stat to="/language/review" Icon={LanguageIcon} tone={toDo ? 'low' : 'ok'} value={toDo ? toDo.toLocaleString() : 'Done'}
        label="Cards to review" sub={`streak ${plural(s.streak.current, 'day')}`} />
      <Stat to="/language/today" Icon={TrophyIcon} tone={s.minutes_week >= s.goal_week ? 'ok' : 'teal'} value={minutesText(s.minutes_week)}
        label="Language study this week" sub={`goal ${minutesText(s.goal_week)} · ${s.input_hours.toLocaleString()} h input`} />
    </>
  )
}
