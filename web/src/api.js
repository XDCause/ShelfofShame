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

const json = (method, data) => ({ method, body: JSON.stringify(data) })

export const api = {
  listSupplies: (filters = {}) => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v))
    return request(`/supplies?${params}`)
  },
  getSupply: (id) => request(`/supplies/${id}`),
  createSupply: (data) => request('/supplies', json('POST', data)),
  updateSupply: (id, data) => request(`/supplies/${id}`, json('PATCH', data)),
  adjustQty: (id, delta) => request(`/supplies/${id}/adjust`, json('POST', { delta })),
  deleteSupply: (id) => request(`/supplies/${id}`, { method: 'DELETE' }),
  supplyHistory: (id, limit = 20) => request(`/supplies/${id}/history?limit=${limit}`),
  recentHistory: (limit = 50) => request(`/history?limit=${limit}`),
  wishRestock: () => request('/wishlist/restock', { method: 'POST' }),

  listWishlist: (show = 'all') => request(`/wishlist?show=${show}`),
  addWish: (data) => request('/wishlist', json('POST', data)),
  updateWish: (id, data) => request(`/wishlist/${id}`, json('PATCH', data)),
  deleteWish: (id) => request(`/wishlist/${id}`, { method: 'DELETE' }),
  buyWish: (id, purchased_from) => request(`/wishlist/${id}/buy`, json('POST', { purchased_from })),
  buyTicked: (purchased_from) => request('/wishlist/buy-ticked', json('POST', { purchased_from })),
  scan: (barcode) => request(`/scan/${encodeURIComponent(barcode)}`),
  setBarcode: (brand_id, product_code, barcode) =>
    request('/product-barcode', json('PUT', { brand_id, product_code, barcode })),
  lookupTamiya: (code, refresh = false) =>
    request(`/lookup/tamiya/${encodeURIComponent(code)}${refresh ? '?refresh=true' : ''}`),

  listModels: () => request('/models'),
  getModel: (id) => request(`/models/${id}`),
  addModel: (data) => request('/models', json('POST', data)),
  updateModel: (id, data) => request(`/models/${id}`, json('PATCH', data)),
  deleteModel: (id) => request(`/models/${id}`, { method: 'DELETE' }),
  addModelPaints: (id, text, purpose) => request(`/models/${id}/paints`, json('POST', { text, purpose })),
  updateModelPaint: (id, data) => request(`/model-paints/${id}`, json('PATCH', data)),
  deleteModelPaint: (id) => request(`/model-paints/${id}`, { method: 'DELETE' }),
  wishMissingPaints: (id) => request(`/models/${id}/wishlist`, { method: 'POST' }),
  lookupHasegawa: (code, refresh = false) =>
    request(`/lookup/hasegawa/${encodeURIComponent(code)}${refresh ? '?refresh=true' : ''}`),

  lookups: () => request('/lookups'),
  addLookup: (kind, name) => request(`/lookups/${kind}`, json('POST', { name })),
  deleteLookup: (kind, id) => request(`/lookups/${kind}/${id}`, { method: 'DELETE' }),
}

// The photo's last-updated time goes in the URL, so a replaced photo gets a new URL and the
// browser doesn't keep showing its cached copy of the old one.
export const imageUrl = (item) =>
  `/api/product-images/${item.product_info_id}?v=${encodeURIComponent(item.photo_updated ?? '')}`

// Your own photo for any brand + code. The file itself is the request body.
export const uploadPhoto = (brandId, productCode, blob) =>
  request(`/product-photo?brand_id=${brandId}&product_code=${encodeURIComponent(productCode)}`, {
    method: 'PUT',
    body: blob,
    headers: { 'Content-Type': blob.type },
  })
export const deletePhoto = (brandId, productCode) =>
  request(`/product-photo?brand_id=${brandId}&product_code=${encodeURIComponent(productCode)}`, {
    method: 'DELETE',
  })

export const money = (n) =>
  n == null || n === '' ? '' : Number(n).toLocaleString('en-AU', { style: 'currency', currency: 'AUD' })
