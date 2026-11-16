// Pure helpers for the ballistic solver's page bits (the maths itself is api/app/ballistics.py).

// The predicted table beside your own DOPE: for each predicted distance, what you confirmed or entered there (a DOPE row
// with source 'confirmed' / 'entered' at the same metres) and the gap, in the scope's unit. Estimates aren't yours.
export function compareWithDope(predicted, dopeRows) {
  const yours = new Map((dopeRows ?? []).filter((r) => r.source !== 'estimate' && r.elevation != null).map((r) => [r.m, r]))
  return (predicted ?? []).map((p) => {
    const mine = yours.get(p.m)
    return { ...p, mine: mine ? mine.elevation : null, source: mine ? mine.source : null,
      gap: mine ? Math.round((mine.elevation - p.elevation) * 100) / 100 : null }
  })
}

// "Clicks" for an elevation in the scope's unit (null when the rifle has no click size).
export const clicksFor = (value, click) => (value == null || !click ? null : Math.round(value / click))

// How the gap reads: "+0.3 MOA (yours needs more)".
export function gapText(gap, unit) {
  if (gap == null) return ''
  if (Math.abs(gap) < 0.05) return 'agrees'
  return `${gap > 0 ? '+' : '-'}${Math.abs(gap).toFixed(2)} ${unit} (${gap > 0 ? 'yours needs more' : 'yours needs less'})`
}

// A session's weather as a one-line label for a picker.
export function airLabel(s) {
  const bits = [s.temp_c != null && `${s.temp_c}°C`, s.pressure_hpa != null && `${s.pressure_hpa} hPa`, s.humidity_pct != null && `${s.humidity_pct}%`]
  return bits.filter(Boolean).join(', ')
}
