// Where and when a JPEG photo was taken, from its EXIF data - read in the browser BEFORE the photo is
// shrunk (shrinking redraws it, which drops EXIF). Only the few tags the hike needs:
//   GPS: latitude / longitude (degrees, minutes, seconds + N/S/E/W)
//   DateTimeOriginal "2026:09:06 07:20:00" (the camera's clock, no zone) + OffsetTimeOriginal "+10:00" if there
// Returns { lat, lon, taken } with any of them null. Not a JPEG, or no EXIF: all null.
export async function readExif(file) {
  const none = { lat: null, lon: null, taken: null }
  if (!/jpe?g$/i.test(file.type) && !/\.jpe?g$/i.test(file.name)) return none
  const v = new DataView(await file.slice(0, 256 * 1024).arrayBuffer())
  if (v.byteLength < 4 || v.getUint16(0) !== 0xffd8) return none
  let at = 2
  while (at + 4 < v.byteLength) {
    const marker = v.getUint16(at)
    const size = v.getUint16(at + 2)
    if (marker === 0xffe1 && v.getUint32(at + 4) === 0x45786966) return tiff(v, at + 10) // "Exif"
    if ((marker & 0xff00) !== 0xff00 || marker === 0xffda) break                          // image data: no EXIF
    at += 2 + size
  }
  return none
}

function tiff(v, base) {
  const little = v.getUint16(base) === 0x4949
  const u16 = (o) => v.getUint16(base + o, little)
  const u32 = (o) => v.getUint32(base + o, little)
  const ifd = (o) => {
    const tags = {}
    const n = u16(o)
    for (let i = 0; i < n; i++) {
      const e = o + 2 + i * 12
      tags[u16(e)] = { type: u16(e + 2), count: u32(e + 4), at: e + 8 }
    }
    return tags
  }
  const ascii = (t) => {
    if (!t) return null
    const o = t.count > 4 ? u32(t.at) : t.at
    let s = ''
    for (let i = 0; i < t.count - 1; i++) s += String.fromCharCode(v.getUint8(base + o + i))
    return s.trim() || null
  }
  const rationals = (t) => {
    if (!t) return null
    const o = u32(t.at)
    return Array.from({ length: t.count }, (_, i) => u32(o + i * 8) / (u32(o + i * 8 + 4) || 1))
  }
  const degrees = (t, ref, negative) => {
    const d = rationals(t)
    if (!d || d.length < 3) return null
    const value = d[0] + d[1] / 60 + d[2] / 3600
    return ascii(ref) === negative ? -value : value
  }
  try {
    const ifd0 = ifd(u32(4))
    const exif = ifd0[0x8769] ? ifd(u32(ifd0[0x8769].at)) : {}
    const gps = ifd0[0x8825] ? ifd(u32(ifd0[0x8825].at)) : {}
    let lat = degrees(gps[2], gps[1], 'S')
    let lon = degrees(gps[4], gps[3], 'W')
    if (lat === 0 && lon === 0) lat = lon = null             // "no fix" written as 0, 0
    const stamp = ascii(exif[0x9003]) ?? ascii(ifd0[0x0132])  // DateTimeOriginal, else DateTime
    const m = stamp?.match(/^(\d{4}):(\d\d):(\d\d) (\d\d):(\d\d):(\d\d)/)
    const offset = ascii(exif[0x9011])
    const taken = m ? `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}${/^[+-]\d\d:\d\d$/.test(offset ?? '') ? offset : ''}` : null
    return { lat: Number.isFinite(lat) ? lat : null, lon: Number.isFinite(lon) ? lon : null, taken }
  } catch {
    return { lat: null, lon: null, taken: null }      // a damaged EXIF block: just no position
  }
}
