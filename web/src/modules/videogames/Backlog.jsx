import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../../core/app-context.js'
import { PICKS, pickDetail, STATUSES, STATUS_LABEL } from './backlogHelpers.js'
import { GamePicture } from './steam.jsx'

// Set a game's status (the game panel). "Not set" keeps the API's guess, shown in brackets.
export function StatusPicker({ game, other, otherId, onSaved }) {
  const [error, setError] = useState('')
  const save = async (value) => {
    setError('')
    try {
      onSaved(await (other ? api.setOtherGameStatus(otherId, value || null) : api.setVideoGameStatus(game.app_id, value || null)))
    } catch (e) {
      setError(e.message)
    }
  }
  return (
    <div className="vgb-status">
      <label className="field"><span className="field-label">Status</span>
        <select value={game.play_status ?? ''} onChange={(e) => save(e.target.value)}>
          <option value="">Not set ({STATUS_LABEL[game.status]})</option>
          {STATUSES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select></label>
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}

// The dashboard's "What next?": a game from your Backlog - the shortest, the fewest achievements left, or any one.
export function WhatNextCard({ platforms }) {
  const { openPanel, refreshKey } = useApp()
  const [by, setBy] = useState('shortest')
  const [data, setData] = useState(null)
  const key = platforms?.join(',') ?? ''
  const load = useCallback(() => api.videoGameBacklog(by, key ? key.split(',') : null).then(setData).catch(() => setData(null)),
    [by, key])
  useEffect(() => { load() }, [load, refreshKey])
  const pick = data?.pick
  return (
    <section className="card home-card vgb-next">
      <h2 className="home-card-title">What next?</h2>
      <div className="chip-row" role="group" aria-label="Pick by">
        {PICKS.map(([id, label]) => (
          <button key={id} type="button" className="chip-filter" aria-pressed={by === id} onClick={() => setBy(id)}>{label}</button>
        ))}
      </div>
      {!data ? <p className="muted small">Loading...</p> : !pick ? (
        <p className="muted small">Nothing in your Backlog. Set a game's status to Backlog to put it here.</p>
      ) : (
        <>
          <button type="button" className="row-button vgb-pick" onClick={() => openPanel('videogame', { id: pick.app_id })}>
            <GamePicture game={pick} className="game-capsule" />
            <span className="grow">
              <span className="item-title">{pick.name}</span>
              <span className="item-meta">{pickDetail(pick, data.median_finished_minutes) || 'No time or achievements known'}</span>
            </span>
          </button>
          {by === 'random' && <button type="button" className="secondary small" onClick={load}>Pick another</button>}
          {data.others.length > 0 && by !== 'random' && (
            <ul className="list compact">
              {data.others.map((g) => (
                <li key={`${g.platform}${g.app_id}`}><button type="button" className="row-button" onClick={() => openPanel('videogame', { id: g.app_id })}>
                  <span className="grow item-title">{g.name}</span><span className="muted small">{pickDetail(g, data.median_finished_minutes)}</span></button></li>
              ))}
            </ul>
          )}
          <p className="muted small">{data.count} game{data.count === 1 ? '' : 's'} in your Backlog.</p>
        </>
      )}
    </section>
  )
}
