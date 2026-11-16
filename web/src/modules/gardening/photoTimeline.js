// Pure helpers for a plant's photo timeline (tested in web/src/tests/photoTimeline.test.js).

const DAY = 86400000
const dayNumber = (iso) => Math.round(Date.parse(`${String(iso).slice(0, 10)}T00:00:00Z`) / DAY)

// Every photo on a plant's notes, oldest first: [{photo_id, url, on, text}].
export function photosByDate(logs) {
  const out = []
  for (const l of logs ?? []) {
    for (const p of l.photos ?? []) out.push({ photo_id: p.photo_id, url: p.url, on: String(l.happened_on).slice(0, 10), text: l.text ?? null })
  }
  return out.sort((a, b) => (a.on === b.on ? a.photo_id - b.photo_id : a.on < b.on ? -1 : 1))
}

// "Day 12" counting from when it was started ("Day 0" on the day; "Before it started" if the photo is older).
export function dayLabel(on, startedOn) {
  if (!on || !startedOn) return ''
  const d = dayNumber(on) - dayNumber(startedOn)
  return d < 0 ? 'Before it started' : `Day ${d}`
}

// "3 weeks" / "5 days" / "same day" between two photos.
export function spanText(a, b) {
  const d = Math.abs(dayNumber(b) - dayNumber(a))
  if (d === 0) return 'same day'
  if (d < 14) return `${d} day${d === 1 ? '' : 's'}`
  if (d < 60) return `${Math.round(d / 7)} weeks`
  return `${Math.round(d / 30.4)} months`
}

// The pair to compare at first: the oldest and the newest photo.
export function firstPair(photos) {
  return photos.length ? [photos[0].photo_id, photos[photos.length - 1].photo_id] : [null, null]
}
