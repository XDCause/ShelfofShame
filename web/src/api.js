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
  // What you've done lately (core): stock, kits, build log, time, journal
  activity: (limit = 20) => request(`/activity?limit=${limit}`),

  // Journal (core): pages, tags, @mentions, photos, drawings
  listPages: (params = {}) => request(`/journal?${new URLSearchParams(Object.entries(params).filter(([, v]) => v))}`),
  addPage: (page = {}) => request('/journal', send('POST', page)),
  getPage: (id) => request(`/journal/${id}`),
  updatePage: (id, data) => request(`/journal/${id}`, send('PATCH', data)),
  deletePage: (id) => request(`/journal/${id}`, send('DELETE')),
  journalTags: () => request('/journal/tags'),
  moods: (start, end) => request(`/journal/moods?start=${start}&end=${end}`),
  mentionable: (q) => request(`/journal/mentionable?q=${enc(q)}`),
  listTodos: (done = false) => request(`/journal/todos${done ? '?done=true' : ''}`),
  tickTodo: (pageId, blockId, checked) => request(`/journal/${pageId}/todos/${enc(blockId)}`, send('PATCH', { checked })),
  applySuggestion: (pageId, key) => request(`/journal/${pageId}/suggestions/apply`, send('POST', { key })),
  dismissSuggestion: (pageId, key) => request(`/journal/${pageId}/suggestions/dismiss`, send('POST', { key })),
  addDrawing: (pageId) => request(`/journal/${pageId}/drawings`, send('POST')),
  getDrawing: (id) => request(`/journal/drawings/${id}`),
  saveDrawing: (id, scene) => request(`/journal/drawings/${id}`, send('PUT', scene)),
  addDrawingFiles: (id, files) => request(`/journal/drawings/${id}/files`, send('PUT', files)),
  saveDrawingPreview: (id, blob) => request(`/journal/drawings/${id}/preview`, image('PUT', blob)),
  uploadJournalImage: (blob, pageId) => request(`/journal/images${pageId ? `?page_id=${pageId}` : ''}`, image('POST', blob)),

  // Calendar (core): events (repeats expanded by the API) and what happened each day
  calendar: (start, end) => request(`/calendar?start=${start}&end=${end}`),
  upcoming: (limit = 5) => request(`/calendar/upcoming?limit=${limit}`),
  getEvent: (id) => request(`/calendar/events/${id}`),
  addEvent: (data) => request('/calendar/events', send('POST', data)),
  updateEvent: (id, data) => request(`/calendar/events/${id}`, send('PATCH', data)),
  deleteEvent: (id) => request(`/calendar/events/${id}`, send('DELETE')),
  skipEventDay: (id, day) => request(`/calendar/events/${id}/skip`, send('POST', { day })),

  // Hobby supplies: the inventory
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
  addSupplyToWishlist: (id) => request(`/supplies/${id}/wishlist`, send('POST')),
  removeSupplyFromWishlist: (id) => request(`/supplies/${id}/wishlist`, send('DELETE')),

  // Wishlist
  listWishlist: () => request('/wishlist'),
  addWish: (data) => request('/wishlist', send('POST', data)),
  updateWish: (id, data) => request(`/wishlist/${id}`, send('PATCH', data)),
  deleteWish: (id) => request(`/wishlist/${id}`, send('DELETE')),
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

  // Board games
  listBoardGames: () => request('/board-games'),
  boardGameSummary: () => request('/board-games/summary'),
  getBoardGame: (id) => request(`/board-games/${id}`),
  addBoardGame: (data) => request('/board-games', send('POST', data)),
  updateBoardGame: (id, data) => request(`/board-games/${id}`, send('PATCH', data)),
  deleteBoardGame: (id) => request(`/board-games/${id}`, send('DELETE')),
  listPlays: (limit = 200) => request(`/board-games/plays?limit=${limit}`),
  addPlay: (gameId, data) => request(`/board-games/${gameId}/plays`, send('POST', data)),
  deletePlay: (id) => request(`/board-game-plays/${id}`, send('DELETE')),

  // Volleyball: games, gear, videos
  listVolleyball: () => request('/volleyball/games'),
  volleyballSummary: () => request('/volleyball/summary'),
  getVolleyball: (id) => request(`/volleyball/games/${id}`),
  addVolleyball: (data) => request('/volleyball/games', send('POST', data)),
  updateVolleyball: (id, data) => request(`/volleyball/games/${id}`, send('PATCH', data)),
  deleteVolleyball: (id) => request(`/volleyball/games/${id}`, send('DELETE')),
  listGear: () => request('/gear'),
  getGear: (id) => request(`/gear/${id}`),
  addGear: (data) => request('/gear', send('POST', data)),
  updateGear: (id, data) => request(`/gear/${id}`, send('PATCH', data)),
  deleteGear: (id) => request(`/gear/${id}`, send('DELETE')),
  listVideos: () => request('/volleyball/videos'),
  addVideo: (data) => request('/volleyball/videos', send('POST', data)),
  updateVideo: (id, data) => request(`/volleyball/videos/${id}`, send('PATCH', data)),
  deleteVideo: (id) => request(`/volleyball/videos/${id}`, send('DELETE')),

  // Video games (Steam achievements)
  steamAccount: () => request('/videogames/account'),
  setSteamProfile: (profile) => request('/videogames/account', send('PUT', { profile })),
  syncSteam: (full = false) => request(`/videogames/sync${full ? '?full=true' : ''}`, send('POST')),
  videoGameSummary: () => request('/videogames/summary'),
  listVideoGames: (show = 'all') => request(`/videogames?show=${show}`),
  getVideoGame: (id) => request(`/videogames/${id}`),
  hideVideoGame: (id, hidden) => request(`/videogames/${id}`, send('PATCH', { hidden })),
  setVideoGameGoal: (percent) => request('/videogames/goal', send('PUT', { percent })),
  videoGameStats: () => request('/videogames/stats'),
  videoGameRecap: (month) => request(`/videogames/recap${month ? `?month=${month}` : ''}`),
  addExtraVideoGame: (game) => request('/videogames/extra', send('POST', { game })),
  otherGames: () => request('/videogames/other'),
  otherAccount: () => request('/videogames/other/account'),
  setOtherAccount: (profile) => request('/videogames/other/account', send('PUT', { profile })),
  addOtherGame: (game) => request('/videogames/other', send('POST', game)),
  updateOtherGame: (id, data) => request(`/videogames/other/${id}`, send('PATCH', data)),
  deleteOtherGame: (id) => request(`/videogames/other/${id}`, send('DELETE')),
  removeExtraVideoGame: (id) => request(`/videogames/extra/${id}`, send('DELETE')),

  // A photo kept on its own row (board games, gear): path = '/board-games/3' or '/gear/2'
  uploadRowPhoto: (path, blob) => request(`${path}/photo`, image('PUT', blob)),
  deleteRowPhoto: (path) => request(`${path}/photo`, send('DELETE')),

  // Time and the build log
  runningTimer: () => request('/timer'),
  startTimer: (id) => request(`/models/${id}/timer/start`, send('POST')),
  stopTimer: (id, note) => request(`/models/${id}/timer/stop`, send('POST', { note })),
  addSession: (id, data) => request(`/models/${id}/sessions`, send('POST', data)),
  deleteSession: (id) => request(`/model-sessions/${id}`, send('DELETE')),
  addLogEntry: (id, data) => request(`/models/${id}/log`, send('POST', data)),
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
export const logPhotoUrl = (entry) => `/api/model-log/${entry.entry_id}/photo?v=${enc(entry.photo_updated ?? entry.created_at)}`

// The photo's last-updated time goes in the URL, so a replaced photo gets a new URL and the
// browser doesn't keep showing its cached copy of the old one.
export const imageUrl = (item) =>
  `/api/product-images/${item.product_info_id}?v=${enc(item.photo_updated ?? '')}`

// "just now", "5 min ago", "2h ago", "yesterday", "3 days ago", else the date.
export const timeAgo = (when) => {
  const minutes = (Date.now() - new Date(when).getTime()) / 60000
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${Math.floor(minutes)} min ago`
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)}h ago`
  const days = Math.floor(minutes / (24 * 60))
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return shortDate(when)
}

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
export const isoDay = (d) => d.toLocaleDateString('en-CA')         // a Date -> YYYY-MM-DD (local)
export const dayDate = (iso) => new Date(`${iso}T12:00:00`)          // YYYY-MM-DD -> a Date at midday

// "19:00:00" -> "7pm", "19:30:00" -> "7:30pm"
export const clock = (hms) => {
  if (!hms) return ''
  const [h, m] = hms.split(':').map(Number)
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, '0')}` : ''}${h < 12 ? 'am' : 'pm'}`
}
