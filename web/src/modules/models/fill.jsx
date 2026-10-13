// How full a supply is, judging by its condition (there's no measuring a paint pot). Used for the
// fill bars: Home's "Running low", the inventory list and the item panel.
export const FILL = { Sealed: 100, Opened: 85, 'Half used': 50, 'Nearly empty': 15, Empty: 0, 'Dried out': 0 }

export const fillOf = (supply) => (supply.qty_on_hand <= 0 ? 0 : FILL[supply.condition] ?? 100)

// Red when nearly gone, amber when getting there, green otherwise.
export const fillTone = (percent) => (percent < 20 ? 'out' : percent < 60 ? 'low' : 'ok')

export function FillBar({ percent, label }) {
  return (
    <span className={`fill-bar ${fillTone(percent)}`} role="meter" aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={percent} aria-label={label ?? `About ${percent}% left`}>
      <span style={{ width: `${Math.max(percent, 3)}%` }} />
    </span>
  )
}
