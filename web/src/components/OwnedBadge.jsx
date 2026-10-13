// What your inventory says about an item (wishlist cards and Shop Tamiya results):
//   red    "None left"                  - used up (0 on hand)
//   amber  "You own 1 · Nearly empty"   - running out, so fine to rebuy
//   grey   "You own 1 · Sealed"         - you still have a good one: don't double-buy
// Expects owned_supply_id, owned_qty, owned_condition and owned_status from the API.
export default function OwnedBadge({ wish }) {
  if (wish.owned_supply_id == null) return null
  if (wish.owned_qty <= 0) return <span className="badge out">None left</span>
  const own = `You own ${wish.owned_qty}${wish.owned_condition ? ` · ${wish.owned_condition}` : ''}`
  return <span className={`badge ${wish.owned_status === 'OK' ? 'own' : 'low'}`}>{own}</span>
}
