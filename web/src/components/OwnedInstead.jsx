import { useEffect, useState } from 'react'
import { api } from '../api.js'

// On a supply that's Low or Out: the paints you DO own that are close to it, in any brand (your own colour matches,
// the same colour code, the same colour name) - so you can paint today and buy later (api/app/colours.py).
export default function OwnedInstead({ item, onOpenItem }) {
  const [list, setList] = useState(null)
  useEffect(() => {
    api.ownedInstead(item.brand_id, item.product_code, item.name).then(setList).catch(() => setList([]))
  }, [item.brand_id, item.product_code, item.name])
  if (!list || list.length === 0) return null
  return (
    <section className="panel-section oin-box">
      <h4 className="section-title">{item.qty_on_hand <= 0 ? 'Out of this? ' : 'Running low? '}You own something close</h4>
      <ul className="oin-list">
        {list.map((a) => (
          <li key={a.supply_id}>
            <button type="button" className="link-plain" onClick={() => onOpenItem(a.supply_id)}>{a.name}</button>
            <span className="muted small"> · {a.how} · {a.qty} in stock</span>
          </li>
        ))}
      </ul>
      <p className="muted small">A match is a guide, not a guarantee: try it on a spare piece first.</p>
    </section>
  )
}
