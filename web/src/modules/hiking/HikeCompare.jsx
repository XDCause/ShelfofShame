import { useEffect, useState } from 'react'
import { api, shortDate } from '../../api.js'
import Fold from '../../components/Fold.jsx'
import { hikeTime, km } from './hikingParts.jsx'
import { gapLabel, splitTally } from './hikingMath.js'

// The same trail again: your other hikes on it (same trail name, or the same start and finish), the best time,
// where this one ranks, and kilometre by kilometre against the best (api/app/hikepace.py).
export default function HikeCompare({ hikeId, onOpen }) {
  const [r, setR] = useState(null)
  useEffect(() => { api.hikeSameTrail(hikeId).then(setR).catch(() => setR(null)) }, [hikeId])
  const c = r?.compare
  if (!c) return null
  const mine = c.runs.find((x) => x.is_this)
  const tally = splitTally(r.split_gaps)
  return (
    <section className="panel-section">
      <Fold title="Same trail" detail={`${c.of} runs · ${c.rank === 1 ? 'your best' : `#${c.rank}`}`}>
        <p className="small hike-same-sum">
          {c.rank === 1 ? <>Your <strong>best time</strong> on this trail: {hikeTime(mine.seconds)}.</>
            : <>{gapLabel(c.behind_best_s)} behind your best ({hikeTime(c.runs.find((x) => x.is_best).seconds)}).</>}
          {' '}Average {hikeTime(c.average_s)}.
        </p>
        <table className="hike-splits hike-same-table">
          <thead><tr><th scope="col">Date</th><th scope="col">Time</th><th scope="col">Distance</th><th scope="col">vs best</th></tr></thead>
          <tbody>
            {c.runs.map((x) => (
              <tr key={x.hike_id} className={`${x.is_best ? 'fastest' : ''} ${x.is_this ? 'hike-same-this' : ''}`}>
                <td>{x.is_this ? 'This hike' : <button type="button" className="plain small" onClick={() => onOpen?.(x.hike_id)}>{shortDate(x.hiked_on)}</button>}</td>
                <td>{hikeTime(x.seconds)}</td><td>{km(x.distance_m)}</td>
                <td>{x.is_best ? 'best' : gapLabel(x.seconds - c.runs.find((b) => b.is_best).seconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {r.split_gaps.length > 0 && (
          <>
            <p className="small muted">Against your best, kilometre by kilometre: {tally.quicker} quicker, {tally.slower} slower.</p>
            <ol className="hike-same-gaps">
              {r.split_gaps.map((g) => (
                <li key={g.km} className={g.gap_s <= 0 ? 'quicker' : 'slower'}><span>km {g.km}</span> <strong>{gapLabel(g.gap_s)}</strong></li>
              ))}
            </ol>
          </>
        )}
      </Fold>
    </section>
  )
}
