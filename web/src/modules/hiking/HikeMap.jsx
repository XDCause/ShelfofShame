import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { km, metres } from './hikingParts.jsx'

// The route on a real map (Leaflet, an open-source map library): a topographic map (OpenTopoMap -
// contours, tracks, peaks; from OpenStreetMap data) or satellite photos (Esri World Imagery), your
// photos as thumbnail pins where they were taken, landmarks near the track with their photo, start /
// finish, and `at` = the point being hovered on the elevation profile. The map pictures (tiles) come
// straight from those services, with their credit line in the corner as they ask.
const BASES = {
  topo: {
    label: 'Topo', url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', subdomains: 'abc', maxZoom: 17,
    attribution: 'Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM · '
      + 'Style © <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
  },
  satellite: {
    label: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    maxZoom: 19, attribution: 'Imagery © Esri, Maxar, Earthstar Geographics and the GIS User Community',
  },
}
const remembered = () => { try { return localStorage.getItem('hike-map-base') || 'topo' } catch { return 'topo' } }
const colour = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#15803d'

// A popup's content, built as elements (names come from OpenStreetMap: never put them in as HTML).
function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props)
  children.filter(Boolean).forEach((c) => node.append(c))
  return node
}
function landmarkPopup(lm) {
  const facts = [lm.label, lm.ele != null && `${lm.ele.toLocaleString()} m`, `${km(lm.along_m)} in`,
    lm.off_m > 30 && `${metres(lm.off_m)} off the track`].filter(Boolean).join(' · ')
  return el('div', { className: 'hike-popup' },
    el('strong', { textContent: lm.name ?? lm.label }),
    el('span', { className: 'muted', textContent: facts }),
    lm.photo && el('a', { href: lm.photo.page, target: '_blank', rel: 'noreferrer' },
      el('img', { src: lm.photo.thumb, alt: lm.name ?? lm.label, loading: 'lazy', referrerPolicy: 'no-referrer' })),
    lm.photo && el('span', { className: 'hike-credit', textContent: [lm.photo.author, lm.photo.licence, 'Wikimedia Commons'].filter(Boolean).join(' · ') }))
}

export default function HikeMap({ track, waypoints = [], photos = [], landmarks = [], at = null, loop = false, onPhoto }) {
  const box = useRef(null)
  const map = useRef(null)
  const tiles = useRef(null)
  const marks = useRef(null)
  const here = useRef(null)
  const [base, setBase] = useState(remembered)

  useEffect(() => {          // the map and the route, once per track
    const m = L.map(box.current, { scrollWheelZoom: false, zoomSnap: 0.25 })
    const line = track.map((p) => [p[0], p[1]])
    L.polyline(line, { color: '#ffffff', weight: 7, opacity: 0.85, interactive: false }).addTo(m)
    L.polyline(line, { color: colour('--ok'), weight: 4, interactive: false }).addTo(m)
    const dot = (p, fill, title) => L.circleMarker([p[0], p[1]], { radius: 7, color: '#fff', weight: 2, fillColor: fill, fillOpacity: 1 })
      .bindTooltip(title).addTo(m)
    if (!loop) dot(track[track.length - 1], colour('--out'), 'Finish')
    dot(track[0], colour('--ok'), loop ? 'Start and finish' : 'Start')
    m.fitBounds(L.latLngBounds(line), { padding: [24, 24] })
    marks.current = L.layerGroup().addTo(m)
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [track, loop])

  useEffect(() => {          // Topo or Satellite
    const m = map.current
    if (!m) return
    const b = BASES[base] ?? BASES.topo
    tiles.current?.remove()
    tiles.current = L.tileLayer(b.url, { subdomains: b.subdomains ?? 'abc', maxZoom: b.maxZoom, attribution: b.attribution,
      referrerPolicy: 'strict-origin-when-cross-origin', className: `hike-tiles-${base}` }).addTo(m)
    tiles.current.bringToBack()
    try { localStorage.setItem('hike-map-base', base) } catch { /* a private window: just not remembered */ }
  }, [base, track])

  useEffect(() => {          // waypoints, landmarks, your photos
    const group = marks.current
    if (!group) return
    group.clearLayers()
    for (const w of waypoints) {
      L.circleMarker([w.lat, w.lon], { radius: 5, color: '#fff', weight: 2, fillColor: colour('--purple'), fillOpacity: 1 })
        .bindTooltip(w.name ?? 'Waypoint').addTo(group)
    }
    for (const lm of landmarks) {
      L.marker([lm.lat, lm.lon], {
        icon: L.divIcon({ className: 'hike-landmark-pin', html: '<span></span>', iconSize: [16, 16] }),
        title: lm.name ?? lm.label, keyboard: true, alt: lm.name ?? lm.label,
      }).bindPopup(() => landmarkPopup(lm), { maxWidth: 260 }).addTo(group)
    }
    for (const p of photos) {
      if (p.lat == null) continue
      const img = el('img', { src: p.url, alt: '' })
      L.marker([p.lat, p.lon], {
        icon: L.divIcon({ className: 'hike-photo-pin', html: img.outerHTML, iconSize: [40, 40], iconAnchor: [20, 46] }),
        title: p.caption ?? 'Your photo', alt: p.caption ?? 'Your photo', riseOnHover: true,
      }).on('click', () => onPhoto?.(p)).addTo(group)
    }
  }, [waypoints, landmarks, photos, track, onPhoto])

  useEffect(() => {          // the hovered point
    const m = map.current
    if (!m) return
    here.current?.remove()
    here.current = at != null && track[at]
      ? L.circleMarker([track[at][0], track[at][1]], { radius: 7, color: '#fff', weight: 2, fillColor: colour('--tint'), fillOpacity: 1, interactive: false }).addTo(m)
      : null
  }, [at, track])

  return (
    <figure className="hike-map-frame">
      <div className="segmented hike-map-bases" role="group" aria-label="Map">
        {Object.entries(BASES).map(([id, b]) => (
          <button key={id} type="button" aria-pressed={base === id} onClick={() => setBase(id)}>{b.label}</button>
        ))}
      </div>
      <div ref={box} className="hike-map-box" role="region" aria-label={`Map of the route${loop ? ', a loop' : ''}`} />
      <figcaption className="hike-map-key">
        <span><i className="hike-key-start" /> {loop ? 'Start / finish' : 'Start'}</span>
        {!loop && <span><i className="hike-key-end" /> Finish</span>}
        {landmarks.length > 0 && <span><i className="hike-key-landmark" /> Landmark</span>}
        {photos.some((p) => p.lat != null) && <span><i className="hike-key-photo" /> Your photo</span>}
        <span className="muted">Scroll the page, not the map: zoom with + / −</span>
      </figcaption>
    </figure>
  )
}
