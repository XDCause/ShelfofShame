// Every call to the backend goes through here. The browser only ever talks to /api/...,
// which nginx forwards to the API container. The front end never touches the database.

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  if (res.status === 204) return null
  const body = await res.json().catch(() => null)
  if (!res.ok) throw Object.assign(new Error(errorMessage(body) || `${res.status} ${res.statusText}`), { status: res.status })
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

// A picture from a web address, fetched by the API (api/app/webphoto.py) and handed back as a Blob.
export async function photoFromUrl(url) {
  const res = await fetch('/api/photo-from-url', { ...send('POST', { url }), headers: { 'Content-Type': 'application/json' } })
  if (!res.ok) throw new Error(errorMessage(await res.json().catch(() => null)) || `${res.status} ${res.statusText}`)
  return res.blob()
}

const send = (method, data) => ({ method, body: data === undefined ? undefined : JSON.stringify(data) })
const enc = encodeURIComponent
// Query string from an object, leaving out empty values.
const query = (params) => new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''))
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

  // Goals (core): details, steps, a number to track and dated progress notes
  goals: (status) => request(`/goals${status ? `?status=${status}` : ''}`),
  getGoal: (id) => request(`/goals/${id}`),
  addGoal: (goal) => request('/goals', send('POST', goal)),
  updateGoal: (id, changes) => request(`/goals/${id}`, send('PATCH', changes)),
  deleteGoal: (id) => request(`/goals/${id}`, send('DELETE')),
  addGoalStep: (id, text) => request(`/goals/${id}/steps`, send('POST', { text })),
  updateGoalStep: (stepId, changes) => request(`/goal-steps/${stepId}`, send('PATCH', changes)),
  deleteGoalStep: (stepId) => request(`/goal-steps/${stepId}`, send('DELETE')),
  orderGoalSteps: (id, stepIds) => request(`/goals/${id}/steps/order`, send('PUT', { step_ids: stepIds })),
  addGoalUpdate: (id, note) => request(`/goals/${id}/updates`, send('POST', note)),
  deleteGoalUpdate: (updateId) => request(`/goal-updates/${updateId}`, send('DELETE')),

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
  // Add a supply's look-up: Tamiya and / or Trumpeter by what you typed -> {found: [{maker, ...}], missed}
  lookupItem: (code) => request(`/lookup/item/${enc(code)}`),
  // A Trumpeter kit or tool by the 5-digit item number on the box (00968)
  lookupTrumpeter: (code, refresh = false) =>
    request(`/lookup/trumpeter/${enc(code)}${refresh ? '?refresh=true' : ''}`),
  // A Bandai kit via hlj.com: your code (G5057403), barcode, HLJ code or a name ({choices} if several)
  lookupBandai: (code, refresh = false) => request(`/lookup/bandai/${enc(code)}${refresh ? '?refresh=true' : ''}`),
  // Warhammer kits from Good Games: a name ({choices}), GW code (59-05), box barcode or id:<product>
  lookupWarhammer: (code, refresh = false) => request(`/lookup/warhammer/${enc(code)}${refresh ? '?refresh=true' : ''}`),
  warhammerArmy: (name, refresh = false) => request(`/warhammer/army?name=${enc(name)}${refresh ? '&refresh=true' : ''}`),
  warhammerArmies: () => request('/warhammer/armies'),
  wantWarhammer: (id) => request('/warhammer/want', send('POST', { id })),
  // Gundam kits from Good Games: words, box code or barcode; none = everything in stock now
  gundamKits: (q = '', refresh = false) => request(`/gundam/kits?${new URLSearchParams({ ...(q ? { q } : {}), ...(refresh ? { refresh: 'true' } : {}) })}`),
  wantGundam: (id) => request('/gundam/want', send('POST', { id })),
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
  minisFromBox: (id) => request(`/models/${id}/minis/from-box`, send('POST')),
  addMinis: (id, unit, count) => request(`/models/${id}/minis`, send('POST', { unit, count })),
  updateMini: (miniId, data) => request(`/model-minis/${miniId}`, send('PATCH', data)),
  setMinisStage: (id, miniIds, stage) => request(`/models/${id}/minis/stage`, send('PUT', { mini_ids: miniIds, stage })),
  renameMiniUnit: (id, unit, to) => request(`/models/${id}/minis/unit`, send('PUT', { unit, to })),
  deleteMiniUnit: (id, unit) => request(`/models/${id}/minis?unit=${encodeURIComponent(unit)}`, send('DELETE')),
  deleteModelPaint: (id) => request(`/model-paints/${id}`, send('DELETE')),
  // All the missing paints, or one checklist line (paintId = its model_paint_id).
  wishMissingPaints: (id, paintId) => request(`/models/${id}/wishlist${paintId ? `?paint_id=${paintId}` : ''}`, send('POST')),
  kitPaints: (id) => request(`/models/${id}/kit-paints`),
  addKitPaints: (id, paints) => request(`/models/${id}/kit-paints`, send('POST', { paints })),

  // Board games
  listBoardGames: () => request('/board-games'),
  boardGameSummary: () => request('/board-games/summary'),
  getBoardGame: (id) => request(`/board-games/${id}`),
  addBoardGame: (data) => request('/board-games', send('POST', data)),
  // Gameology: board games matching a name; fill in a game you have from one (blanks only unless replace)
  // Gameology first, Good Games for the holes (more = ask Good Games too): {results, asked_good_games, notes}
  boardGameLookup: (q, more = false) => request(`/board-games/lookup?q=${encodeURIComponent(q)}${more ? '&more=true' : ''}`),
  // r = a lookup result (Gameology: its handle; Good Games: its product number)
  boardGameFromShop: (id, r, replace = false) => request(`/board-games/${id}/shop`, send('POST', { ...shopRef(r), replace })),
  updateBoardGame: (id, data) => request(`/board-games/${id}`, send('PATCH', data)),
  deleteBoardGame: (id) => request(`/board-games/${id}`, send('DELETE')),
  listPlays: (limit = 200) => request(`/board-games/plays?limit=${limit}`),
  wanted: () => request('/wanted'),
  gearLookup: (q) => request(`/gear/lookup?q=${encodeURIComponent(q)}`),
  linkGearToShop: (id, shopId) => request(`/gear/${id}/shop`, send('POST', { shop_id: shopId })),
  coachNotes: () => request('/volleyball/coach'),
  coachStarter: () => request('/volleyball/coach/starter', send('POST')),
  addCoachNote: (note) => request('/volleyball/coach', send('POST', note)),
  updateCoachNote: (id, note) => request(`/volleyball/coach/${id}`, send('PATCH', note)),
  deleteCoachNote: (id) => request(`/volleyball/coach/${id}`, send('DELETE')),
  addPlayElsewhere: (play) => request('/board-games/plays', send('POST', play)),
  addPlay: (gameId, data) => request(`/board-games/${gameId}/plays`, send('POST', data)),
  deletePlay: (id) => request(`/board-game-plays/${id}`, send('DELETE')),

  // Volleyball: games, gear, videos
  listVolleyball: () => request('/volleyball/games'),
  volleyballSummary: () => request('/volleyball/summary'),
  getVolleyball: (id) => request(`/volleyball/games/${id}`),
  addVolleyball: (data) => request('/volleyball/games', send('POST', data)),
  updateVolleyball: (id, data) => request(`/volleyball/games/${id}`, send('PATCH', data)),
  deleteVolleyball: (id) => request(`/volleyball/games/${id}`, send('DELETE')),
  volleyballTeams: () => request('/volleyball/teams'),
  addTeam: (data) => request('/volleyball/teams', send('POST', data)),
  updateTeam: (id, data) => request(`/volleyball/teams/${id}`, send('PATCH', data)),
  deleteTeam: (id) => request(`/volleyball/teams/${id}`, send('DELETE')),
  listGear: (hobby) => request(`/gear${hobby ? `?hobby=${hobby}` : ''}`),
  getGear: (id) => request(`/gear/${id}`),
  addGear: (data) => request('/gear', send('POST', data)),
  updateGear: (id, data) => request(`/gear/${id}`, send('PATCH', data)),
  deleteGear: (id) => request(`/gear/${id}`, send('DELETE')),
  listVideos: () => request('/volleyball/videos'),
  // A video file, sent as it is (XMLHttpRequest, so the upload can report its progress: onProgress(0-1)).
  uploadVideo: (id, file, onProgress) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', `/api/volleyball/videos/${id}/file`)
    xhr.setRequestHeader('Content-Type', videoType(file))
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name))
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let body = null
      try { body = JSON.parse(xhr.responseText) } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body)
      else reject(new Error(errorMessage(body) || (xhr.status === 413 ? 'That video is too big (4 GB at most).' : `Upload failed (${xhr.status})`)))
    }
    xhr.onerror = () => reject(new Error('The upload stopped - check the connection and try again.'))
    xhr.send(file)
  }),
  addVideo: (data) => request('/volleyball/videos', send('POST', data)),
  updateVideo: (id, data) => request(`/volleyball/videos/${id}`, send('PATCH', data)),
  deleteVideo: (id) => request(`/volleyball/videos/${id}`, send('DELETE')),
  videoClips: (id) => request(`/volleyball/videos/${id}/clips`),
  addClip: (id, clip) => request(`/volleyball/videos/${id}/clips`, send('POST', clip)),
  deleteClip: (clipId) => request(`/volleyball/clips/${clipId}`, send('DELETE')),
  makeHighlights: (title, clipIds) => request('/volleyball/highlights', send('POST', { title, clip_ids: clipIds })),
  highlightProgress: (id) => request(`/volleyball/highlights/${id}`),

  // Video games (Steam achievements)
  steamAccount: () => request('/videogames/account'),
  setSteamProfile: (profile) => request('/videogames/account', send('PUT', { profile })),
  syncSteam: (full = false) => request(`/videogames/sync${full ? '?full=true' : ''}`, send('POST')),
  // platforms: a list like ['steam', 'epic'] to count only those; leave it out for all of them.
  videoGameSummary: (platforms) => request(`/videogames/summary${platforms ? `?platforms=${platforms.join(',')}` : ''}`),
  listVideoGames: (show = 'all') => request(`/videogames?show=${show}`),
  getVideoGame: (id) => request(`/videogames/${id}`),
  // Just this game, now: answers with the game (and sync_note if SteamHunters / Exophase didn't answer)
  syncVideoGame: (id) => request(`/videogames/${id}/sync`, send('POST')),
  hideVideoGame: (id, hidden) => request(`/videogames/${id}`, send('PATCH', { hidden })),
  setVideoGameGoal: (percent) => request('/videogames/goal', send('PUT', { percent })),
  // What you played each day lately (totals saved each sync; api/app/vgplaytime.py)
  videoGamePlaytime: (days, platforms) => request(`/videogames/playtime?${query({ days, platforms: platforms?.join(',') })}`),
  videoGameStats: (platforms) => request(`/videogames/stats${platforms ? `?platforms=${platforms.join(',')}` : ''}`),
  videoGameRecap: (month, platforms) => request(`/videogames/recap?${new URLSearchParams({
    ...(month && { month }), ...(platforms && { platforms: platforms.join(',') }) })}`),
  addExtraVideoGame: (game) => request('/videogames/extra', send('POST', { game })),
  videoGameFriends: () => request('/videogames/friends'),
  refreshFriends: (force = false) => request(`/videogames/friends/refresh${force ? '?force=true' : ''}`, send('POST')),
  addFriend: (profile) => request('/videogames/friends', send('POST', { profile })),
  videoGameFriend: (id) => request(`/videogames/friends/${id}`),
  compareFriend: (id) => request(`/videogames/friends/${id}/compare`, send('POST')),
  removeFriend: (id) => request(`/videogames/friends/${id}`, send('DELETE')),
  findSteamGames: (q) => request(`/videogames/find?q=${encodeURIComponent(q)}`),
  scoutVideoGame: (appId) => request(`/videogames/scout/${appId}`),
  findOtherGames: (platform, q) => request(`/videogames/other/find?platform=${platform}&q=${encodeURIComponent(q)}`),
  otherGames: () => request('/videogames/other'),

  // Chess
  readingLookup: (q) => request(`/reading/lookup?q=${encodeURIComponent(q)}`),
  books: (params = {}) => request(`/reading/books?${new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''))}`),
  book: (id) => request(`/reading/books/${id}`),
  addBook: (book) => request('/reading/books', send('POST', book)),
  updateBook: (id, data) => request(`/reading/books/${id}`, send('PATCH', data)),
  deleteBook: (id) => request(`/reading/books/${id}`, send('DELETE')),
  bookProgress: (id, data) => request(`/reading/books/${id}/progress`, send('POST', data)),
  deleteReadingLog: (logId) => request(`/reading/log/${logId}`, send('DELETE')),
  addQuote: (id, quote) => request(`/reading/books/${id}/quotes`, send('POST', quote)),
  deleteQuote: (quoteId) => request(`/reading/quotes/${quoteId}`, send('DELETE')),
  quotes: (q = '') => request(`/reading/quotes?q=${encodeURIComponent(q)}`),
  readingSummary: () => request('/reading/summary'),
  readingStats: (months = 24) => request(`/reading/stats?months=${months}`),
  setReadingGoal: (books) => request('/reading/goal', send('PUT', { books })),
  // Travel (api/app/travel.py: trips, places, countries, the dashboard; travel_trip.py: what's on a trip). Every
  // change to a trip's bookings, plan, money, packing, journal or photos answers with the whole trip.
  travelLists: () => request('/travel/lists'),
  travelSummary: () => request('/travel/summary'),
  travelSettings: () => request('/travel/settings'),
  saveTravelSettings: (data) => request('/travel/settings', send('PUT', data)),
  trips: (phase) => request(`/travel/trips?${query({ phase })}`),
  trip: (id) => request(`/travel/trips/${id}`),
  addTrip: (data) => request('/travel/trips', send('POST', data)),
  updateTrip: (id, data) => request(`/travel/trips/${id}`, send('PATCH', data)),
  deleteTrip: (id) => request(`/travel/trips/${id}`, send('DELETE')),
  setTripCover: (id, blob) => request(`/travel/trips/${id}/photo`, image('PUT', blob)),
  removeTripCover: (id) => request(`/travel/trips/${id}/photo`, send('DELETE')),
  travelPlaces: (shown) => request(`/travel/places?${query({ shown })}`),
  addTravelPlace: (data) => request('/travel/places', send('POST', data)),
  updateTravelPlace: (id, data) => request(`/travel/places/${id}`, send('PATCH', data)),
  deleteTravelPlace: (id) => request(`/travel/places/${id}`, send('DELETE')),
  orderTripStops: (id, placeIds) => request(`/travel/trips/${id}/stops`, send('PUT', { place_ids: placeIds })),
  findTravelPlace: (q) => request(`/travel/find-place?${query({ q })}`),
  travelCountries: () => request('/travel/countries'),
  setTravelCountry: (code, data) => request(`/travel/countries/${code}`, send('PUT', data)),
  forgetTravelCountry: (code) => request(`/travel/countries/${code}`, send('DELETE')),
  addBooking: (tripId, data) => request(`/travel/trips/${tripId}/bookings`, send('POST', data)),
  updateBooking: (id, data) => request(`/travel/bookings/${id}`, send('PATCH', data)),
  deleteBooking: (id) => request(`/travel/bookings/${id}`, send('DELETE')),
  addPlanItem: (tripId, data) => request(`/travel/trips/${tripId}/plan`, send('POST', data)),
  updatePlanItem: (id, data) => request(`/travel/plan/${id}`, send('PATCH', data)),
  deletePlanItem: (id) => request(`/travel/plan/${id}`, send('DELETE')),
  addExpense: (tripId, data) => request(`/travel/trips/${tripId}/expenses`, send('POST', data)),
  updateExpense: (id, data) => request(`/travel/expenses/${id}`, send('PATCH', data)),
  deleteExpense: (id) => request(`/travel/expenses/${id}`, send('DELETE')),
  setTripRate: (tripId, currency, rate, apply = false) => request(`/travel/trips/${tripId}/rates/${currency}?${query({ apply: apply || null })}`,
    send('PUT', { rate })),
  travelRates: () => request('/travel/rates'),
  addPacking: (tripId, data) => request(`/travel/trips/${tripId}/packing`, send('POST', data)),
  packFromList: (tripId, listId) => request(`/travel/trips/${tripId}/packing/from-list`, send('POST', { list_id: listId })),
  packGear: (tripId, hobby) => request(`/travel/trips/${tripId}/packing/gear`, send('POST', { hobby })),
  unpackAll: (tripId) => request(`/travel/trips/${tripId}/packing/unpack`, send('POST')),
  updatePacking: (id, data) => request(`/travel/packing/${id}`, send('PATCH', data)),
  deletePacking: (id) => request(`/travel/packing/${id}`, send('DELETE')),
  packingLists: () => request('/travel/packing-lists'),
  addPackingList: (data) => request('/travel/packing-lists', send('POST', data)),
  updatePackingList: (id, data) => request(`/travel/packing-lists/${id}`, send('PATCH', data)),
  deletePackingList: (id) => request(`/travel/packing-lists/${id}`, send('DELETE')),
  saveTripEntry: (tripId, day, text) => request(`/travel/trips/${tripId}/entries/${day}`, send('PUT', { text })),
  addTripPhoto: (tripId, blob, { lat, lon, taken, day } = {}) => request(`/travel/trips/${tripId}/photos?${query({ lat, lon, taken, day })}`,
    image('POST', blob)),
  updateTripPhoto: (id, data) => request(`/travel/photos/${id}`, send('PATCH', data)),
  deleteTripPhoto: (id) => request(`/travel/photos/${id}`, send('DELETE')),
  travelPhotos: () => request('/travel/photos'),

  // Precision shooting (api/app/shooting.py: rifles, ammo, ranges, settings; shooting_sessions.py: sessions, groups, DOPE)
  shootingLists: () => request('/shooting/lists'),
  shootingSettings: () => request('/shooting/settings'),
  saveShootingSettings: (data) => request('/shooting/settings', send('PUT', data)),
  shootingSummary: () => request('/shooting/summary'),
  shootingRanges: () => request('/shooting/ranges'),
  addShootingRange: (data) => request('/shooting/ranges', send('POST', data)),
  updateShootingRange: (id, data) => request(`/shooting/ranges/${id}`, send('PATCH', data)),
  deleteShootingRange: (id) => request(`/shooting/ranges/${id}`, send('DELETE')),
  rifles: () => request('/shooting/rifles'),
  rifle: (id) => request(`/shooting/rifles/${id}`),
  addRifle: (data) => request('/shooting/rifles', send('POST', data)),
  updateRifle: (id, data) => request(`/shooting/rifles/${id}`, send('PATCH', data)),
  deleteRifle: (id) => request(`/shooting/rifles/${id}`, send('DELETE')),
  addRifleLog: (id, data) => request(`/shooting/rifles/${id}/logs`, send('POST', data)),
  deleteRifleLog: (logId) => request(`/shooting/rifle-logs/${logId}`, send('DELETE')),
  ammoList: () => request('/shooting/ammo'),
  ammo: (id) => request(`/shooting/ammo/${id}`),
  addAmmo: (data) => request('/shooting/ammo', send('POST', data)),
  updateAmmo: (id, data) => request(`/shooting/ammo/${id}`, send('PATCH', data)),
  deleteAmmo: (id) => request(`/shooting/ammo/${id}`, send('DELETE')),
  ammoBox: (id, data) => request(`/shooting/ammo/${id}/box`, send('POST', data)),
  shootingSessions: (params = {}) => request(`/shooting/sessions?${query(params)}`),
  shootingSession: (id) => request(`/shooting/sessions/${id}`),
  addShootingSession: (data) => request('/shooting/sessions', send('POST', data)),
  updateShootingSession: (id, data) => request(`/shooting/sessions/${id}`, send('PATCH', data)),
  deleteShootingSession: (id) => request(`/shooting/sessions/${id}`, send('DELETE')),
  addShootingGroup: (sessionId, data) => request(`/shooting/sessions/${sessionId}/groups`, send('POST', data)),
  updateShootingGroup: (id, data) => request(`/shooting/groups/${id}`, send('PATCH', data)),
  deleteShootingGroup: (id) => request(`/shooting/groups/${id}`, send('DELETE')),
  // Shot by shot, and a session's photos and videos (api/app/shooting_shots.py) - each answers with the whole session
  // A kit's parts, each a supply of its own (part_of the kit): [{name, category_id?, qty_on_hand?, notes?}]
  addSupplyParts: (id, parts) => request(`/supplies/${id}/parts`, send('POST', { parts })),
  addShot: (groupId, data) => request(`/shooting/groups/${groupId}/shots`, send('POST', data)),
  updateShot: (id, data) => request(`/shooting/shots/${id}`, send('PATCH', data)),
  deleteShot: (id) => request(`/shooting/shots/${id}`, send('DELETE')),
  addShootPhoto: (sessionId, blob, params = {}) => request(`/shooting/sessions/${sessionId}/photos?${query(params)}`, image('POST', blob)),
  // A video straight off the phone (XMLHttpRequest, so the upload can report its progress: onProgress(0-1)).
  addShootVideo: (sessionId, file, params = {}, onProgress) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/shooting/sessions/${sessionId}/videos?${query(params)}`)
    xhr.setRequestHeader('Content-Type', videoType(file))
    xhr.setRequestHeader('X-File-Name', encodeURIComponent(file.name))
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total)
    xhr.onload = () => {
      let body = null
      try { body = JSON.parse(xhr.responseText) } catch { /* not JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body)
      else reject(new Error(errorMessage(body) || (xhr.status === 413 ? 'That video is too big (4 GB at most).' : `Upload failed (${xhr.status})`)))
    }
    xhr.onerror = () => reject(new Error("Couldn't reach the app to upload the video."))
    xhr.send(file)
  }),
  updateShootMedia: (id, data) => request(`/shooting/media/${id}`, send('PATCH', data)),
  deleteShootMedia: (id) => request(`/shooting/media/${id}`, send('DELETE')),
  dope: (rifleId, ammoId) => request(`/shooting/dope?${query({ rifle_id: rifleId, ammo_id: ammoId })}`),
  addDope: (data) => request('/shooting/dope', send('POST', data)),
  deleteDope: (id) => request(`/shooting/dope/${id}`, send('DELETE')),
  // Hiking (api/app/hiking.py): a GPX file goes up as-is, like a photo.
  hikes: (params = {}) => request(`/hiking/hikes?${new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''))}`),
  hike: (id) => request(`/hiking/hikes/${id}`),
  addHike: (hike) => request('/hiking/hikes', send('POST', hike)),
  updateHike: (id, data) => request(`/hiking/hikes/${id}`, send('PATCH', data)),
  deleteHike: (id) => request(`/hiking/hikes/${id}`, send('DELETE')),
  importHike: (file) => request(`/hiking/import?filename=${enc(file.name)}`,
    { method: 'POST', headers: { 'Content-Type': 'application/gpx+xml' }, body: file }),
  hikingSummary: () => request('/hiking/summary'),
  addHikePhoto: (id, blob, { lat, lon, taken } = {}) => request(`/hiking/hikes/${id}/photos?${new URLSearchParams(
    Object.entries({ lat, lon, taken }).filter(([, v]) => v != null))}`, image('POST', blob)),
  updateHikePhoto: (photoId, caption) => request(`/hiking/photos/${photoId}`, send('PATCH', { caption })),
  deleteHikePhoto: (photoId) => request(`/hiking/photos/${photoId}`, send('DELETE')),
  setHikeGear: (id, gearIds) => request(`/hiking/hikes/${id}/gear`, send('PUT', { gear_ids: gearIds })),
  lookAgainHike: (id) => request(`/hiking/hikes/${id}/landmarks`, send('POST')),
  // Gardening (api/app/garden.py, garden_guide.py, garden_items.py)
  gardenLists: () => request('/garden/lists'),
  gardenSettings: () => request('/garden/settings'),
  saveGardenSettings: (data) => request('/garden/settings', send('PUT', data)),
  gardenPlaces: (q) => request(`/garden/places?q=${enc(q)}`),
  gardenToday: () => request('/garden/today'),
  gardenSummary: () => request('/garden/summary'),
  gardenSpaces: () => request('/garden/spaces'),
  gardenSpace: (id) => request(`/garden/spaces/${id}`),
  addGardenSpace: (data) => request('/garden/spaces', send('POST', data)),
  updateGardenSpace: (id, data) => request(`/garden/spaces/${id}`, send('PATCH', data)),
  deleteGardenSpace: (id) => request(`/garden/spaces/${id}`, send('DELETE')),
  gardenContainers: () => request('/garden/containers'),
  gardenContainer: (id) => request(`/garden/containers/${id}`),
  addGardenContainer: (data) => request('/garden/containers', send('POST', data)),
  updateGardenContainer: (id, data) => request(`/garden/containers/${id}`, send('PATCH', data)),
  copyGardenContainer: (id) => request(`/garden/containers/${id}/copy`, send('POST')),
  deleteGardenContainer: (id) => request(`/garden/containers/${id}`, send('DELETE')),
  gardenPlantings: (params = {}) => request(`/garden/plantings?${query(params)}`),
  gardenPlanting: (id) => request(`/garden/plantings/${id}`),
  addGardenPlanting: (data) => request('/garden/plantings', send('POST', data)),
  updateGardenPlanting: (id, data) => request(`/garden/plantings/${id}`, send('PATCH', data)),
  deleteGardenPlanting: (id) => request(`/garden/plantings/${id}`, send('DELETE')),
  propagatePlanting: (id, data) => request(`/garden/plantings/${id}/propagate`, send('POST', data)),
  gardenCare: (data) => request('/garden/care', send('POST', data)),
  addGardenLog: (data) => request('/garden/logs', send('POST', data)),
  deleteGardenLog: (id) => request(`/garden/logs/${id}`, send('DELETE')),
  addGardenPhoto: (logId, blob) => request(`/garden/logs/${logId}/photos`, image('POST', blob)),
  deleteGardenPhoto: (id) => request(`/garden/photos/${id}`, send('DELETE')),
  gardenPhotos: (params = {}) => request(`/garden/photos?${query(params)}`),
  gardenTasks: () => request('/garden/tasks'),
  addGardenTask: (data) => request('/garden/tasks', send('POST', data)),
  gardenTaskDone: (id) => request(`/garden/tasks/${id}/done`, send('POST')),
  deleteGardenTask: (id) => request(`/garden/tasks/${id}`, send('DELETE')),
  gardenHarvests: (year) => request(`/garden/harvests${year ? `?year=${year}` : ''}`),
  gardenGuides: (params = {}) => request(`/garden/guides?${query(params)}`),
  gardenGuide: (id) => request(`/garden/guides/${id}`),
  addGardenGuide: (data) => request('/garden/guides', send('POST', data)),
  copyGardenGuide: (id) => request(`/garden/guides/${id}/copy`, send('POST')),
  updateGardenGuide: (id, data) => request(`/garden/guides/${id}`, send('PATCH', data)),
  deleteGardenGuide: (id) => request(`/garden/guides/${id}`, send('DELETE')),
  gardenSowNow: () => request('/garden/sow-now'),
  gardenItems: (params = {}) => request(`/garden/items?${query(params)}`),
  gardenItem: (id) => request(`/garden/items/${id}`),
  addGardenItem: (data) => request('/garden/items', send('POST', data)),
  addGardenItemFromPage: (data) => request('/garden/items/from-page', send('POST', data)),
  addGardenItemFromBunnings: (data) => request('/garden/items/bunnings', send('POST', data)),
  refreshGardenItem: (id, url) => request(`/garden/items/${id}/bunnings`, send('POST', url ? { url } : {})),
  updateGardenItem: (id, data) => request(`/garden/items/${id}`, send('PATCH', data)),
  deleteGardenItem: (id) => request(`/garden/items/${id}`, send('DELETE')),
  sowGardenItem: (id, data) => request(`/garden/items/${id}/sow`, send('POST', data)),
  gardenProblems: (params = {}) => request(`/garden/problems?${query(params)}`),
  gardenProblemFound: (id, data) => request(`/garden/problems/${id}/found`, send('POST', data)),
  importGoodreads: (file) => request('/reading/import/goodreads', { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: file }),
  coverStatus: () => request('/reading/covers'),
  bookSeries: (id) => request(`/reading/books/${id}/series`),
  bookRecs: () => request('/reading/recommendations'),
  refreshBookRecs: () => request('/reading/recommendations/refresh', send('POST')),
  wantBookRec: (work) => request(`/reading/recommendations/${work}/want`, send('POST')),
  dismissBookRec: (work) => request(`/reading/recommendations/${work}/dismiss`, send('POST')),
  bringBackBookRecs: () => request('/reading/recommendations/dismissed', send('DELETE')),
  chessAccount: () => request('/chess/account'),
  setChessAccount: (username) => request('/chess/account', send('PUT', { username })),
  syncChess: (full = false) => request(`/chess/sync${full ? '?full=true' : ''}`, send('POST')),
  chessSummary: () => request('/chess/summary'),
  chessRatings: (days = 365) => request(`/chess/ratings?days=${days}`),
  chessGames: (params = {}) => request(`/chess/games?${new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ''))}`),
  chessGame: (id) => request(`/chess/games/${id}`),
  addChessGame: (game) => request('/chess/games', send('POST', game)),
  updateChessGame: (id, data) => request(`/chess/games/${id}`, send('PATCH', data)),
  deleteChessGame: (id) => request(`/chess/games/${id}`, send('DELETE')),
  chessOpenings: (colour, timeClass) => request(`/chess/openings?colour=${colour}${timeClass ? `&time_class=${timeClass}` : ''}`),
  otherAccount: () => request('/videogames/other/account'),
  setOtherAccount: (profile) => request('/videogames/other/account', send('PUT', { profile })),
  addOtherGame: (game) => request('/videogames/other', send('POST', game)),
  updateOtherGame: (id, data) => request(`/videogames/other/${id}`, send('PATCH', data)),
  getOtherGame: (id) => request(`/videogames/other/${id}`),
  syncOtherGame: (id) => request(`/videogames/other/${id}/sync`, send('POST')),
  tickOtherAchievement: (id, apiName, achieved) => request(`/videogames/other/${id}/achievements/${encodeURIComponent(apiName)}`,
    send('PUT', { achieved })),
  tickAllOther: (id, achieved) => request(`/videogames/other/${id}/achievements`, send('PUT', { achieved })),
  setOtherSteam: (id, link) => request(`/videogames/other/${id}/steam`, send('PUT', { link })),
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
  updateLogEntry: (entryId, data) => request(`/model-log/${entryId}`, send('PATCH', data)),
  deleteLogEntry: (id) => request(`/model-log/${id}`, send('DELETE')),
  addLogPhoto: (id, blob) => request(`/model-log/${id}/photos`, image('POST', blob)),
  deleteLogPhoto: (photoId) => request(`/model-log-photos/${photoId}`, send('DELETE')),

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

  // Page banners (api/app/banners.py): a picture of your own per area ('home', 'journal', a hobby's id)
  banners: () => request('/banners'),
  setBanner: (area, blob) => request(`/banners/area/${area}/photo`, image('PUT', blob)),
  moveBanner: (area, focusY) => request(`/banners/area/${area}`, send('PATCH', { focus_y: focusY })),
  removeBanner: (area) => request(`/banners/area/${area}/photo`, send('DELETE')),

  // Settings
  settings: () => request('/settings'),
  // The weekly check of the websites the app reads
  siteChecks: () => request('/site-checks'),
  runSiteChecks: () => request('/site-checks/run', send('POST')),
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
export const logPhotoUrl = (photoId) => `/api/model-log-photos/${photoId}`   // a photo never changes: its id is enough

// The photo's last-updated time goes in the URL, so a replaced photo gets a new URL and the
// browser doesn't keep showing its cached copy of the old one.
export const imageUrl = (item) =>
  `/api/product-images/${item.product_info_id}?v=${enc(item.photo_updated ?? '')}`

// "just now", "5 min ago", "2h ago", "yesterday", "3 days ago", else the date.
// Which shop product a board-game lookup result is, as the API wants it.
export const shopRef = (r) => (r.source === 'goodgames' ? { gg_id: r.gg_id } : { shop_handle: r.handle })

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

// A video's type: what the phone says, else from its name (some phones leave .mov blank).
const VIDEO_EXT = { mp4: 'video/mp4', m4v: 'video/x-m4v', mov: 'video/quicktime', webm: 'video/webm', mkv: 'video/x-matroska', '3gp': 'video/3gpp' }
const videoType = (file) => (file.type || VIDEO_EXT[file.name.split('.').pop().toLowerCase()] || 'video/mp4')

// 262144000 -> "250 MB"
export const fileSize = (bytes) => (bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB`
  : bytes >= 1024 ** 2 ? `${Math.round(bytes / 1024 ** 2)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)
