import { useEffect, useState } from 'react'
import { api } from '../api.js'

// Other paints that are (probably) the same colour as one product:
//   Same colour  the same Tamiya code in another range (X-7 enamel = X-7 acrylic): certain
//   Same name    another Tamiya range with the same colour name (LP-28 / TS-5 Olive Drab): likely
//   Your matches colour groups you've made, any brand
export default function ColourMatches({ brandId, productCode, name, onOpenItem, onChanged }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [added, setAdded] = useState({}) // product_code -> true once put on the wishlist

  useEffect(() => {
    api.colourMatches(brandId, productCode, name).then(setData).catch((e) => setError(e.message))
  }, [brandId, productCode, name])

  const wish = async (p) => {
    try {
      await api.addCatalogToWishlist(p.product_code)
      setAdded((a) => ({ ...a, [p.product_code]: true }))
      onChanged?.()
    } catch (e) {
      setError(e.message)
    }
  }

  if (error) return <p className="alert error small">{error}</p>
  if (!data) return <p className="muted small">Looking for matches...</p>
  const { colour, same_code: sameCode, same_name: sameName, groups } = data
  if (!colour && groups.length === 0) {
    return <p className="hint">No colour code to match on. Add your own match on the Colours page.</p>
  }

  const row = (p) => (
    <li key={p.product_code}>
      <span className="grow">{p.name}<span className="muted small block">{p.product_code}</span></span>
      {p.owned_qty > 0 ? (
        <button type="button" className="tag ok as-button" onClick={() => onOpenItem?.(p.owned_supply_id)}>You have {p.owned_qty}</button>
      ) : added[p.product_code] ? <span className="tag">On wishlist</span> : (
        <button type="button" className="plain small" onClick={() => wish(p)}>+ Wishlist</button>
      )}
    </li>
  )

  return (
    <div className="matches">
      {colour && <p className="small">{colour.code} · <strong>{colour.name}</strong></p>}
      {sameCode.length > 0 && (
        <>
          <h5>Same colour, other ranges</h5>
          <ul className="list compact">{sameCode.map(row)}</ul>
        </>
      )}
      {sameName.length > 0 && (
        <>
          <h5>Same name - likely close <span className="muted">(check before relying on it)</span></h5>
          <ul className="list compact">{sameName.map(row)}</ul>
        </>
      )}
      {groups.map((g) => (
        <div key={g.group_id}>
          <h5>Your match: {g.name}{g.note && <span className="muted"> · {g.note}</span>}</h5>
          <ul className="list compact">
            {g.members.filter((m) => m.product_code !== productCode).map((m) => (
              <li key={m.member_id}>
                <span className="grow">{m.paint_name}{m.brand && <span className="muted small block">{m.brand} {m.product_code}</span>}</span>
                {m.owned_qty > 0 && (
                  <button type="button" className="tag ok as-button" onClick={() => onOpenItem?.(m.owned_supply_id)}>You have {m.owned_qty}</button>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {colour && sameCode.length + sameName.length + groups.length === 0 && (
        <p className="hint">No other Tamiya paint has this code or colour name.</p>
      )}
    </div>
  )
}
