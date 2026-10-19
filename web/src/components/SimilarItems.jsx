// "Already in your inventory: ..." while you type a name or code, to avoid double entries.

// Words that say nothing about WHICH item it is.
const FILLER = new Set(['acrylic', 'paint', 'mini', 'tamiya', 'the', 'and', 'for', 'with'])

// "Acrylic XF-1 Flat Black" -> ['xf1', 'flat', 'black'] (XF-1 and XF1 count as the same)
function words(text) {
  return (text ?? '').toLowerCase()
    .replace(/([a-z])-(\d)/g, '$1$2')
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length >= 2 && !FILLER.has(w))
}

function findSimilar(supplies, { name, productCode, brandId }) {
  const typed = words(name)
  const code = (productCode ?? '').trim().toUpperCase()
  if (!typed.length && !code) return []
  return supplies.filter((s) => {
    if (code && s.product_code?.toUpperCase() === code && (!brandId || String(s.brand_id) === String(brandId))) return true
    if (!typed.length) return false
    const have = new Set(words(`${s.name} ${s.product_code ?? ''}`))
    const own = words(s.name)
    // every word typed is in its name - or its (shorter) name is all in what's typed: owning "Single-Blade
    // Nipper" while adding "Stedi MS-106 Precision Single Blade Nipper"
    return typed.every((w) => have.has(w)) || (own.length >= 2 && own.every((w) => typed.includes(w)))
  }).slice(0, 3)
}

export default function SimilarItems({ supplies, name, productCode, brandId, onOpen, label = 'Already in your inventory' }) {
  const matches = findSimilar(supplies, { name, productCode, brandId })
  if (!matches.length) return null
  return (
    <div className="alert low small similar" role="status">
      <strong>{label}:</strong>
      <ul>
        {matches.map((s) => (
          <li key={s.supply_id}>
            {s.item_ref} · {s.name} ({s.qty_on_hand} on hand){s.kit_name && <span className="muted"> · in {s.kit_name}</span>}
            {onOpen && <> <button type="button" className="plain" onClick={() => onOpen(s.supply_id)}>Open</button></>}
          </li>
        ))}
      </ul>
    </div>
  )
}
