// How a technique's solve time compares with the usual time for its level (1 = on par): "20% under", "50% over".
export function parText(v) {
  if (v == null) return '–'
  if (v < 0.95) return `${Math.round((1 - v) * 100)}% under`
  if (v > 1.05) return `${Math.round((v - 1) * 100)}% over`
  return 'on par'
}
