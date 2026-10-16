import { useEffect, useState } from 'react'
import { api, imageUrl } from '../api.js'
import FitTextarea from './FitTextarea.jsx'
import KitPaintsPicker from './KitPaintsPicker.jsx'

// A model's paint checklist. Paints you own are ticked and locked (your inventory says you have
// them); a mix is ticked when you own every part; anything else can be ticked by hand. Missing
// paints that match something you own say so ("You have LP-28 - same name").
export default function PaintChecklist({ model, onModel, run, flash, onOpenSupply }) {
  const [paint, setPaint] = useState({ text: '', purpose: '' })
  const [pasting, setPasting] = useState(false)
  const [pasted, setPasted] = useState('')
  const [picking, setPicking] = useState(false)
  const [supplies, setSupplies] = useState([]) // for the "pick from inventory" suggestions

  useEffect(() => { api.listSupplies().then(setSupplies).catch(() => {}) }, [])

  const addPaints = (text, purpose) => run(async () => {
    onModel(await api.addModelPaints(model.model_id, text, purpose))
    setPaint({ text: '', purpose: '' })
    setPasted('')
    setPasting(false)
  })

  // paint = one checklist line ("+ Wishlist" on its row), or none = every missing paint.
  const wishMissing = (paint) => run(async () => {
    const r = await api.wishMissingPaints(model.model_id, paint?.model_paint_id)
    onModel(r.model)
    flash(r.added.length ? `Added to wishlist: ${r.added.join(', ')}.` : 'Nothing new to add.')
    if (r.skipped.length) throw new Error(`Not added (no brand + code to buy by): ${r.skipped.join(', ')}.`)
  })

  // Show a tick straight away; the server's answer then replaces it (or a reload puts it back).
  const change = (p, data) => {
    if ('have_it' in data) {
      onModel({ ...model, paints: model.paints.map((x) => (x.model_paint_id === p.model_paint_id
        ? { ...x, have_it: data.have_it, have: x.in_inventory || data.have_it } : x)) }, null, false)
    }
    run(async () => {
      try {
        onModel(await api.updateModelPaint(p.model_paint_id, data))
      } catch (e) {
        onModel(await api.getModel(model.model_id))
        throw e
      }
    })
  }

  const buyable = model.paints.filter(canWish)
  const isTamiyaKit = model.brand === 'Tamiya' && model.product_code

  return (
    <section className="panel-section">
      <div className="section-head">
        <h4 className="section-title">Paints {model.paints_total > 0 && `· ${model.paints_have}/${model.paints_total}`}</h4>
        {buyable.length > 0 && (
          <button type="button" className="chip-btn" onClick={() => wishMissing()}>Add {buyable.length} missing to wishlist</button>
        )}
      </div>
      {model.paints_total > 0 && (
        <span className="progress-bar"><span style={{ width: `${(model.paints_have / model.paints_total) * 100}%` }} /></span>
      )}
      {isTamiyaKit && (
        <button type="button" className="secondary kit-paints" onClick={() => setPicking(true)}>
          Pick from Tamiya's paint list for this kit
        </button>
      )}

      <ul className="checklist">
        {model.paints.map((p) => (
          <PaintRow key={p.model_paint_id} paint={p} onOpenSupply={onOpenSupply}
            onChange={(data) => change(p, data)} onWish={() => wishMissing(p)}
            onRemove={() => run(async () => onModel(await api.deleteModelPaint(p.model_paint_id)))} />
        ))}
      </ul>

      {!pasting ? (
        <div className="add-paint">
          <input list="inventory-codes" value={paint.text} placeholder="Paint, e.g. XF-76, or XF-62 + XF-2 (3:1)"
            onChange={(e) => setPaint((x) => ({ ...x, text: e.target.value }))} aria-label="Paint" />
          <input value={paint.purpose} placeholder="What it's for" aria-label="What it's for"
            onChange={(e) => setPaint((x) => ({ ...x, purpose: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter' && paint.text.trim()) addPaints(paint.text, paint.purpose) }} />
          <button type="button" className="secondary" disabled={!paint.text.trim()}
            onClick={() => addPaints(paint.text, paint.purpose)}>Add</button>
          <datalist id="inventory-codes">
            {supplies.filter((s) => s.product_code).map((s) => (
              <option key={s.supply_id} value={s.product_code}>{s.name}</option>
            ))}
          </datalist>
          <button type="button" className="plain" onClick={() => setPasting(true)}>Paste a list</button>
        </div>
      ) : (
        <div className="paste-list">
          <label className="field">
            <span className="field-label">One paint per line, then a tab (or " - ") and what it's for</span>
            <textarea rows="7" value={pasted} onChange={(e) => setPasted(e.target.value)} autoFocus
              placeholder={'XF-76 Grey Green (IJN)\tThe whole exterior\nXF-62 + XF-2 (3:1) - Faded hull'} />
          </label>
          <div className="button-row">
            <button type="button" className="primary" disabled={!pasted.trim()} onClick={() => addPaints(pasted)}>Add paints</button>
            <button type="button" className="plain" onClick={() => setPasting(false)}>Cancel</button>
          </div>
        </div>
      )}

      {picking && (
        <KitPaintsPicker model={model} onClose={() => setPicking(false)}
          onAdded={(m, n) => { onModel(m, `Added ${n} paint${n === 1 ? '' : 's'} from the kit's list ✓`); setPicking(false) }} />
      )}
    </section>
  )
}

// A line you don't have that can go on the wishlist: a paint with a brand + code that isn't on it
// yet, or a mix with a part you're missing.
const canWish = (p) => !p.have && (p.mix ? p.mix.parts.some((x) => x.owned_qty <= 0 && x.product_code)
  : Boolean(p.brand_id && p.product_code && !p.on_wishlist))

function PaintRow({ paint, onChange, onRemove, onOpenSupply, onWish }) {
  const [purpose, setPurpose] = useState(paint.purpose ?? '')
  useEffect(() => setPurpose(paint.purpose ?? ''), [paint.purpose])
  const lowOrOut = paint.in_inventory && paint.stock_status !== 'OK'
  const locked = paint.in_inventory || (paint.mix && paint.have)

  return (
    <li className={paint.have ? 'have' : ''}>
      <label className="check" title={locked ? 'You have it' : 'Tick if you have it'}>
        <input type="checkbox" checked={paint.have} disabled={locked}
          onChange={(e) => onChange({ have_it: e.target.checked })} aria-label={`Have ${paint.paint_name}`} />
        <span aria-hidden="true">✓</span>
      </label>
      {paint.has_image ? <img className="thumb small-thumb" src={imageUrl(paint)} alt="" loading="lazy" />
        : paint.catalog_thumb ? <img className="thumb small-thumb" src={paint.catalog_thumb} alt="" loading="lazy" referrerPolicy="no-referrer" />
        : <span className={paint.mix ? 'thumb small-thumb thumb-empty mix-icon' : 'thumb small-thumb thumb-empty'}>{paint.mix ? '⊕' : ''}</span>}
      <div className="paint-main">
        <div className="paint-name">
          {paint.supply_id
            ? <button type="button" className="link-plain" onClick={() => onOpenSupply(paint.supply_id)}>{paint.paint_name}</button>
            : <span>{paint.paint_name}</span>}
          {paint.mix && <span className="tag">Mix</span>}
          {paint.in_inventory && !lowOrOut && <span className="tag ok">In inventory</span>}
          {lowOrOut && <span className={`badge ${paint.stock_status.toLowerCase()}`}>{paint.condition ?? paint.stock_status}</span>}
          {!paint.have && paint.on_wishlist && <span className="tag">On wishlist</span>}
          {!paint.have && !paint.on_wishlist && paint.product_code && <span className="tag warn">Need to buy</span>}
          {canWish(paint) && (
            <button type="button" className="tag wish-btn" onClick={onWish}
              aria-label={`Add ${paint.paint_name} to the wishlist`}>+ Wishlist</button>
          )}
          {!paint.product_code && !paint.mix && <span className="tag" title="No brand + code, so it can't be matched to your inventory">Not linked</span>}
        </div>
        {paint.mix && (
          <p className="mix-parts small">
            {paint.mix.parts.map((x, i) => (
              <span key={x.part_id} className={x.owned_qty > 0 ? 'ok-text' : 'muted'}>
                {i > 0 && ' + '}{Number(x.parts) !== 1 && `${Number(x.parts)}× `}{x.paint_name}{x.owned_qty > 0 ? ' ✓' : ''}
              </span>
            ))}
          </p>
        )}
        {paint.alternative && (
          <p className="alternative small">
            You have{' '}
            <button type="button" className="plain inline" onClick={() => onOpenSupply(paint.alternative.supply_id)}>
              {paint.alternative.name}</button> · {paint.alternative.how}
          </p>
        )}
        <FitTextarea className="purpose" value={purpose} placeholder="What it's for" aria-label={`What ${paint.paint_name} is for`}
          onChange={(e) => setPurpose(e.target.value)}
          onBlur={() => purpose.trim() !== (paint.purpose ?? '') && onChange({ purpose: purpose.trim() || null })} />
      </div>
      <button type="button" className="icon-btn small remove-paint" onClick={onRemove} aria-label={`Remove ${paint.paint_name}`}>✕</button>
    </li>
  )
}
