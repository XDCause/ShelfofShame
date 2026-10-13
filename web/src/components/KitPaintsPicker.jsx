import { useEffect, useState } from 'react'
import { api } from '../api.js'
import Drawer from './Drawer.jsx'

// The paints Tamiya lists for a kit ("Tamiya Colors required" on the kit's page), grouped as
// on their page. The main X/XF colours are ticked to start with, as the Acrylic Minis you use;
// lacquers, sprays, weathering and tools are there to tick if you want them.
export default function KitPaintsPicker({ model, onClose, onAdded }) {
  const [kit, setKit] = useState(null)
  const [picked, setPicked] = useState(new Set())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.kitPaints(model.model_id).then((k) => {
      setKit(k)
      setPicked(new Set(k.groups.flatMap((g) => g.paints).filter((p) => p.suggested && !p.on_model).map((p) => p.product_code)))
    }).catch((e) => setError(e.message))
  }, [model.model_id])

  const toggle = (code) => setPicked((s) => {
    const next = new Set(s)
    next.has(code) ? next.delete(code) : next.add(code)
    return next
  })

  const add = async () => {
    setBusy(true)
    try {
      const all = kit.groups.flatMap((g) => g.paints)
      const paints = [...picked].map((code) => all.find((p) => p.product_code === code))
        .map(({ product_code, paint_name }) => ({ product_code, paint_name }))
      onAdded(await api.addKitPaints(model.model_id, paints), paints.length)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  const footer = (
    <>
      <button type="button" className="primary" onClick={add} disabled={busy || picked.size === 0}>
        {busy ? 'Adding...' : `Add ${picked.size} paint${picked.size === 1 ? '' : 's'}`}
      </button>
      <button type="button" className="plain" onClick={onClose}>Cancel</button>
    </>
  )

  return (
    <Drawer title="Paints from the kit" onClose={onClose} footer={kit && footer} wide>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!kit && !error && <p className="muted">Reading the kit's page on tamiya.com...</p>}
      {kit && (
        <>
          <p className="small muted">{kit.kit}</p>
          {kit.groups.length === 0 && <p className="empty">Tamiya's page for this kit doesn't list any paints.</p>}
          {kit.groups.map((g) => (
            <section key={g.section} className="panel-section">
              <h4 className="section-title">{g.label}</h4>
              <ul className="list pick-list">
                {g.paints.map((p) => (
                  <li key={p.product_code}>
                    <label className="check-row">
                      <input type="checkbox" checked={p.on_model || picked.has(p.product_code)} disabled={p.on_model}
                        onChange={() => toggle(p.product_code)} />
                      <span className="grow">{p.paint_name}<span className="muted small block">{p.product_code}</span></span>
                      {p.on_model && <span className="tag">On the list</span>}
                      {!p.on_model && p.owned_qty > 0 && <span className="tag ok">You have {p.owned_qty}</span>}
                    </label>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </>
      )}
    </Drawer>
  )
}
