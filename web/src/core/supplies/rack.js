import { familyOf } from '../../components/supplyExtras.jsx'

// The paint-rack view's list (SuppliesTools.jsx PaintRack): paints only, filtered, grouped by brand, each brand in code order.
const byCode = (a, b) => (a.product_code ?? '').localeCompare(b.product_code ?? '', 'en', { numeric: true })
  || a.name.localeCompare(b.name, 'en', { numeric: true })

export function rackGroups(supplies, { brand = '', family = '', text = '', attention = false } = {}) {
  const q = text.trim().toLowerCase()
  const kept = supplies.filter((s) => s.category === 'Paint'
    && (!brand || (s.brand ?? 'No brand') === brand)
    && (!family || familyOf(s.swatch) === family)
    && (!attention || s.stock_status !== 'OK')
    && (!q || `${s.name} ${s.product_code ?? ''}`.toLowerCase().includes(q)))
  const groups = new Map()
  for (const s of kept) {
    const name = s.brand ?? 'No brand'
    if (!groups.has(name)) groups.set(name, [])
    groups.get(name).push(s)
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([name, items]) => ({ brand: name, items: items.sort(byCode) }))
}

// The brands that have paints, for the filter.
export const rackBrands = (supplies) => [...new Set(supplies.filter((s) => s.category === 'Paint').map((s) => s.brand ?? 'No brand'))].sort()
