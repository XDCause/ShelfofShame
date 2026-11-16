// "Can I paint this now?": what a recipe's (or a model's) paints say about your supplies.
// check = { owned, low, out, missing, free, to_buy, ready, items: [{ name, state, supply_id, qty }] } (api/app/recipes.py)
const WORDS = {
  owned: 'you have it', low: 'running low', out: 'out of it', missing: "you don't have it", free: 'not linked to a product',
}

export default function PaintCheck({ check, onWishlist, onOpenSupply, busy = false, showItems = true }) {
  if (!check || check.total === 0) return null
  return (
    <div className="pck-box" role="group" aria-label="Can I paint this now?">
      <p className={check.ready ? 'pck-headline pck-ready' : 'pck-headline'}>
        {check.ready ? 'Ready to paint ✓' : `Not yet: ${check.to_buy} to get`}
        <span className="muted small"> · {check.owned} owned{check.low > 0 && `, ${check.low} low`}{check.out > 0 && `, ${check.out} out`}
          {check.missing > 0 && `, ${check.missing} missing`}{check.free > 0 && `, ${check.free} not checked`}</span>
      </p>
      {showItems && (
        <ul className="pck-list">
          {check.items.map((i, k) => (
            <li key={k} className={`pck-item pck-${i.state}`}>
              {i.supply_id && onOpenSupply
                ? <button type="button" className="link-plain" onClick={() => onOpenSupply(i.supply_id)}>{i.name}</button>
                : <span>{i.name}</span>}
              <span className="pck-state small">{WORDS[i.state]}</span>
            </li>
          ))}
        </ul>
      )}
      {check.to_buy > 0 && onWishlist && (
        <button type="button" className="secondary" disabled={busy} onClick={onWishlist}>
          Add the {check.to_buy} to get to the wishlist
        </button>
      )}
    </div>
  )
}
