import { useState } from 'react'
import { api } from '../../api.js'
import { easiestLocked, estimateText, moneyText, perHourText } from './backlogHelpers.js'

// On the game panel: your own time-to-beat guess (hours) and what you paid, the time to beat that's used (api/app/
// videogames.py with_estimate), cost per hour, and the next easiest achievement. A blank box clears it.
export function GameExtras({ game, other, otherId, onSaved }) {
  const [beat, setBeat] = useState(game.beat_hours ?? '')
  const [price, setPrice] = useState(game.price_paid ?? '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    const data = { beat_hours: beat === '' ? null : Number(beat), price_paid: price === '' ? null : Number(price) }
    try {
      onSaved(await (other ? api.updateOtherGame(otherId, data) : api.setVideoGameDetails(game.app_id, data)))
    } catch (err) {
      setError(err.message)
    }
    setBusy(false)
  }
  const easy = easiestLocked(game.achievements)
  const perHour = game.price_paid != null && game.playtime_minutes > 0 ? game.price_paid / (game.playtime_minutes / 60) : null
  return (
    <form className="vgx-box" onSubmit={save}>
      <div className="vgx-row">
        <label className="field"><span className="field-label">Hours to beat (your guess)</span>
          <input type="number" min="0" step="0.5" inputMode="decimal" value={beat} onChange={(e) => setBeat(e.target.value)} /></label>
        <label className="field"><span className="field-label">Price paid ($)</span>
          <input type="number" min="0" step="0.01" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /></label>
        <button type="submit" className="secondary small" disabled={busy}>Save</button>
      </div>
      {error && <p className="alert error small">{error}</p>}
      {estimateText(game) && <p className="muted small">Time to beat: about {estimateText(game)}</p>}
      {game.price_paid != null && <p className="muted small">Paid {moneyText(game.price_paid)} · {perHourText(perHour)}</p>}
      {easy && <p className="small">Next easiest achievement: <strong>{easy.name}</strong> <span className="muted">({Number(easy.global_percent)}% of players have it)</span></p>}
    </form>
  )
}
