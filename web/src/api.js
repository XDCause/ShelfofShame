// Every call to the backend goes through here. The browser only ever talks to /api/...,
// which nginx forwards to the API container. The front end never touches the database.

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (res.status === 204) return null
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(errorMessage(body) || `${res.status} ${res.statusText}`)
  return body
}

// FastAPI errors are either {detail: "text"} or, for invalid input,
// {detail: [{loc: [..., "field"], msg: "..."}]}.
function errorMessage(body) {
  const detail = body?.detail
  if (Array.isArray(detail)) {
    return detail.map((d) => `${d.loc?.at(-1) ?? 'input'}: ${d.msg}`).join('; ')
  }
  return detail
}

const send = (method, data) => ({ method, body: data === undefined ? undefined : JSON.stringify(data) })
const enc = encodeURIComponent
// An image file as the request body (photos are uploaded as-is, not as JSON).
const image = (method, blob) => ({ method, body: blob, headers: { 'Content-Type': blob.type } })

export const api = {
  // Inventory
  listSupplies: () => request('/supplies'),
  getSupply: (id) => request(`/supplies/${id}`),
  createSupply: (data) => request('/supplies', send('POST', data)),
  updateSupply: (id, data) => request(`/supplies/${id}`, send('PATCH', data)),
  // extra: { undo: true, purchase_date, remove_wish_id } when reversing a mistaken -/+
  adjustQty: (id, delta, extra = {}) => request(`/supplies/${id}/adjust`, send('POST', { delta, ...extra })),
  // alsoWishlist: also take it off the wishlist (used up and not replacing it)
  deleteSupply: (id, alsoWishlist = false) =>
    request(`/supplies/${id}${alsoWishlist ? '?also_wishlist=true' : ''}`, send('DELETE')),
  supplyHistory: (id, limit = 20) => request(`/supplies/${id}/history?limit=${limit}`),
  recentHistory: (limit = 50) => request(`/history?limit=${limit}`),
  addSupplyToWishlist: (id) => request(`/supplies/${id}/wishlist`, send('POST')),

  // Wishlist
  listWishlist: () => request('/wishlist'),
  addWish: (data) => request('/wishlist', send('POST', data)),
  updateWish: (id, data) => request(`/wishlist/${id}`, send('PATCH', data)),
  deleteWish: (id) => request(`/wishlist/${id}`, send('DELETE')),
  buyWish: (id, purchased_from) => request(`/wishlist/${id}/buy`, send('POST', { purchased_from })),
  buyTicked: (purchased_from) => request('/wishlist/buy-ticked', send('POST', { purchased_from })),
  wishRestock: () => request('/wishlist/restock', send('POST')),

  // Products: lookups, barcodes, photos
  scan: (barcode) => request(`/scan/${enc(barcode)}`),
  setBarcode: (brand_id, product_code, barcode) =>
    request('/product-barcode', send('PUT', { brand_id, product_code, barcode })),
  lookupTamiya: (code, refresh = false) => request(`/lookup/tamiya/${enc(code)}${refresh ? '?refresh=true' : ''}`),
  lookupHasegawa: (code, refresh = false) =>
    request(`/lookup/hasegawa/${enc(code)}${refresh ? '?refresh=true' : ''}`),
  // A Bandai kit via hlj.com: your code (G5057403), barcode, HLJ code or a name ({choices} if several)
  lookupBandai: (code, refresh = false) => request(`/lookup/bandai/${enc(code)}${refresh ? '?refresh=true' : ''}`),
  uploadPhoto: (brandId, productCode, blob) =>
    request(`/product-photo?brand_id=${brandId}&product_code=${enc(productCode)}`, image('PUT', blob)),
  deletePhoto: (brandId, productCode) =>
    request(`/product-photo?brand_id=${brandId}&product_code=${enc(productCode)}`, send('DELETE')),

  // Shop Tamiya
  catalogInfo: () => request('/catalog/info'),
  searchCatalog: (q) => request(`/catalog/search?q=${enc(q)}`),
  addCatalogToWishlist: (code) => request(`/catalog/${enc(code)}/wishlist`, send('POST')),
  refreshCatalog: () => request('/catalog/refresh', send('POST')),

  // Models
  listModels: () => request('/models'),
  stashSummary: () => request('/models/summary'),
  getModel: (id) => request(`/models/${id}`),
  addModel: (data) => request('/models', send('POST', data)),
  updateModel: (id, data) => request(`/models/${id}`, send('PATCH', data)),
  deleteModel: (id) => request(`/models/${id}`, send('DELETE')),
  addModelPaints: (id, text, purpose) => request(`/models/${id}/paints`, send('POST', { text, purpose })),
  updateModelPaint: (id, data) => request(`/model-paints/${id}`, send('PATCH', data)),
  deleteModelPaint: (id) => request(`/model-paints/${id}`, send('DELETE')),
  wishMissingPaints: (id) => request(`/models/${id}/wishlist`, send('POST')),
  kitPaints: (id) => request(`/models/${id}/kit-paints`),
  addKitPaints: (id, paints) => request(`/models/${id}/kit-paints`, send('POST', { paints })),

  // Time and the build log
  runningTimer: () => request('/timer'),
  startTimer: (id) => request(`/models/${id}/timer/start`, send('POST')),
  stopTimer: (id, note) => request(`/models/${id}/timer/stop`, send('POST', { note })),
  addSession: (id, data) => request(`/models/${id}/sessions`, send('POST', data)),
  deleteSession: (id) => request(`/model-sessions/${id}`, send('DELETE')),
  addLogEntry: (id, data) => request(`/models/${id}/log`, send('POST', data)),
  updateLogEntry: (id, data) => request(`/model-log/${id}`, send('PATCH', data)),
  deleteLogEntry: (id) => request(`/model-log/${id}`, send('DELETE')),
  addLogPhoto: (id, blob) => request(`/model-log/${id}/photo`, image('PUT', blob)),

  // Colours
  colourMatches: (brandId, productCode, name = '') =>
    request(`/colours/matches?brand_id=${brandId}&product_code=${enc(productCode)}&name=${enc(name)}`),
  listMixes: () => request('/mixes'),
  addMix: (data) => request('/mixes', send('POST', data)),
  updateMix: (id, data) => request(`/mixes/${id}`, send('PATCH', data)),
  deleteMix: (id) => request(`/mixes/${id}`, send('DELETE')),
  listColourGroups: () => request('/colour-groups'),
  addColourGroup: (data) => request('/colour-groups', send('POST', data)),
  updateColourGroup: (id, data) => request(`/colour-groups/${id}`, send('PATCH', data)),
  deleteColourGroup: (id) => request(`/colour-groups/${id}`, send('DELETE')),

  // Settings
  settings: () => request('/settings'),
  updateSettings: (data) => request('/settings', send('PATCH', data)),
  priceGuide: () => request('/price-guide'),
  addPriceRule: (data) => request('/price-guide', send('POST', data)),
  updatePriceRule: (id, data) => request(`/price-guide/${id}`, send('PATCH', data)),
  deletePriceRule: (id) => request(`/price-guide/${id}`, send('DELETE')),
  backups: () => request('/backups'),
  backUpNow: () => request('/backups', send('POST')),
  spending: () => request('/spending'),
  lookups: () => request('/lookups'),
  about: () => request('/about'),
  addLookup: (kind, name) => request(`/lookups/${kind}`, send('POST', { name })),
  deleteLookup: (kind, id) => request(`/lookups/${kind}/${id}`, send('DELETE')),
}

// Plain links (downloads open straight from these).
export const backupUrl = (name) => `/api/backups/${enc(name)}`
export const exportUrl = (kind) => `/api/export/${kind}.csv`
export const logPhotoUrl = (entry) => `/api/model-log/${entry.entry_id}/photo?v=${enc(entry.created_at)}`

// The photo's last-updated time goes in the URL, so a replaced photo gets a new URL and the
// browser doesn't keep showing its cached copy of the old one.
export const imageUrl = (item) =>
  `/api/product-images/${item.product_info_id}?v=${enc(item.photo_updated ?? '')}`

export const money = (n) =>
  n == null || n === '' ? '' : Number(n).toLocaleString('en-AU', { style: 'currency', currency: 'AUD' })

// 135 -> "2 h 15 min", 45 -> "45 min"
export const duration = (minutes) => {
  const m = Math.max(0, Math.round(minutes ?? 0))
  if (m < 60) return `${m} min`
  return m % 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m / 60} h`
}

export const shortDate = (iso) =>
  iso ? new Date(iso.length === 10 ? `${iso}T00:00` : iso)
    .toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }) : ''

export const today = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local time
