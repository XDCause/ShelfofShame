import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { TECHNIQUE } from './engine.js'
import { clockText } from './sudokuParts.js'
import { parText } from './techniqueHelpers.js'

// Stats > By technique (api/app/sudoku.py technique-stats): for each technique, the hints you asked for it, how many
// puzzles you solved that needed it, how long those took against the usual time for their level, and a suggestion for
// what to practise. Solve times by difficulty sit beside it.
export default function TechniqueStats() {
  const { refreshKey } = useApp()
  const [data, setData] = useState(null)
  useEffect(() => { api.sudokuTechniqueStats().then(setData).catch(() => setData(null)) }, [refreshKey])
  if (!data || (!data.techniques.length && !data.difficulties.length)) return null
  const rows = data.techniques.filter((t) => TECHNIQUE[t.key])
  const weakest = data.weakest && TECHNIQUE[data.weakest]
  return (
    <section className="card">
      <h3 className="section-title">By technique</h3>
      {weakest && (
        <p className="small">You ask for the most help with the <strong>{weakest.name}</strong>.{' '}
          <Link to={`/sudoku/play?practice=${data.weakest}`}>Practise it</Link> or <Link to={`/sudoku/learn#${data.weakest}`}>read how it works</Link>.</p>
      )}
      {rows.length > 0 && (
        <div className="sdk-tech-wrap">
          <table className="sdk-tech-table">
            <caption className="visually-hidden">Per technique: hints asked, puzzles that needed it, solve time against par, practice puzzles solved</caption>
            <thead><tr><th scope="col">Technique</th><th scope="col">Hints</th><th scope="col">Puzzles</th><th scope="col">Solve time</th><th scope="col">Practised</th></tr></thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.key}>
                  <th scope="row"><Link to={`/sudoku/learn#${t.key}`}>{TECHNIQUE[t.key].name}</Link></th>
                  <td>{t.hints}</td><td>{t.needed}</td>
                  <td title={t.avg_seconds ? `Average ${clockText(t.avg_seconds)} for puzzles that needed it` : ''}>{t.avg_seconds ? `${clockText(t.avg_seconds)} · ${parText(t.vs_par)}` : '–'}</td>
                  <td>{t.practised}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.difficulties.length > 0 && (
        <p className="muted small">By difficulty: {data.difficulties.map((d) => `${d.difficulty} ${clockText(d.avg_seconds)} average (best ${clockText(d.best_seconds)}, ${d.solved} solved)`).join(' · ')}</p>
      )}
    </section>
  )
}
