import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import { useApp } from '../../core/app-context.js'

// Sudoku's achievements (api/app/sudoku.py ACHIEVEMENTS): worked out from your games, so earlier games count too.
// AwardList shows some (the ones a solve just earned); AwardsView is the page - every group, earned or how far along.

const GROUP_ICON = { Milestones: '🏁', Difficulty: '⛰️', Clean: '✨', Speed: '⚡', Daily: '📅', Weekly: '🗓️', Streaks: '🔥', Learning: '🎓',
  'Hardest 100': '💀', Events: '🗺️', Rank: '🏆', Papers: '📰', Giant: '🧩', Diagonal: '✖️', Habits: '🌙' }

export function AwardList({ awards, compact = false }) {
  return (
    <ul className={`sdk-awards${compact ? ' compact' : ''}`}>
      {awards.map((a) => {
        const got = Boolean(a.unlocked_at)
        return (
          <li key={a.key} className={`sdk-award${got ? ' got' : ''}`}>
            <span className="sdk-award-icon" aria-hidden="true">{GROUP_ICON[a.group] ?? '🏅'}</span>
            <span className="sdk-award-text">
              <strong>{a.name}</strong>
              <span className="muted small">{a.about}</span>
              {got ? <span className="small ok-text">Earned {shortDate(String(a.unlocked_at).slice(0, 10))}</span>
                : a.target > 1 && (
                  <span className="sdk-award-bar" role="img" aria-label={`${a.progress} of ${a.target}`}>
                    <span className="fill-bar tint"><span style={{ width: `${(100 * a.progress) / a.target}%` }} /></span>
                    <span className="muted small">{a.progress} / {a.target}</span>
                  </span>
                )}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export function AwardsView() {
  const { refreshKey } = useApp()
  const [all, setAll] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.sudokuAchievements().then(setAll).catch((e) => setError(e.message)) }, [refreshKey])
  if (error) return <p className="alert error">{error}</p>
  if (!all) return <p className="muted loading">Loading...</p>
  const groups = [...new Set(all.map((a) => a.group))]
  const earned = all.filter((a) => a.unlocked_at).length
  return (
    <section className="page sudoku">
      <section className="card home-card sdk-awards-head">
        <h2 className="home-card-title">Achievements</h2>
        <p><strong className="sdk-done-time">{earned}</strong> <span className="muted">of {all.length} earned</span></p>
        <span className="fill-bar tint" role="img" aria-label={`${earned} of ${all.length} earned`}><span style={{ width: `${(100 * earned) / all.length}%` }} /></span>
      </section>
      {groups.map((g) => {
        const these = all.filter((a) => a.group === g)
        return (
          <section key={g} className="sdk-award-group">
            <h2 className="sdk-learn-head">{GROUP_ICON[g]} {g} <span className="muted small">{these.filter((a) => a.unlocked_at).length} / {these.length}</span></h2>
            <AwardList awards={these} />
          </section>
        )
      })}
    </section>
  )
}
