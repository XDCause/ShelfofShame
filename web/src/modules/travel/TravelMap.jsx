import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'

// Places on a real map (Leaflet, like a hike's): OpenStreetMap's map or Esri's satellite photos, each place a dot
// coloured by where it stands (been / going / want), a trip's stops joined in order (its route), your photos that
// carry GPS as thumbnails, and - while you're placing something - a tap on the map picks the spot. The map
// pictures come straight from those services, with their credit line in the corner as they ask.
const BASES = {
  map: {
    label: 'Map', url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', maxZoom: 19,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  satellite: {
    label: 'Satellite', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    maxZoom: 19, attribution: 'Imagery © Esri, Maxar, Earthstar Geographics and the GIS User Community',
  },
}
const TONES = { Been: '--ok', Planned: '--tint', Want: '--purple' }
const remembered = () => { try { return localStorage.getItem('travel-map-base') || 'map' } catch { return 'map' } }
const colour = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#0a84ff'

// legend: a key of your own instead of Been / Going / Want (the journal's map).
export default function TravelMap({ places = [], photos = [], route = false, picking = false, picked = null, onPick, onPlace,
  onPhoto, label = 'Map of places', legend = null }) {
  const box = useRef(null)
  const map = useRef(null)
  const tiles = useRef(null)
  const marks = useRef(null)
  const pin = useRef(null)
  const fitted = useRef('')
  const [base, setBase] = useState(remembered)
  const pickRef = useRef(onPick)
  useEffect(() => { pickRef.current = picking ? onPick : null }, [picking, onPick])

  useEffect(() => {          // the map, once
    const m = L.map(box.current, { scrollWheelZoom: false, zoomSnap: 0.5, worldCopyJump: true }).setView([-25, 134], 3)
    marks.current = L.layerGroup().addTo(m)
    m.on('click', (e) => pickRef.current?.({ lat: Math.round(e.latlng.lat * 1e5) / 1e5, lon: Math.round(L.Util.wrapNum(e.latlng.lng, [-180, 180], true) * 1e5) / 1e5 }))
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [])

  useEffect(() => {          // Map or Satellite
    const m = map.current
    const b = BASES[base] ?? BASES.map
    tiles.current?.remove()
    tiles.current = L.tileLayer(b.url, { maxZoom: b.maxZoom, attribution: b.attribution,
      referrerPolicy: 'strict-origin-when-cross-origin' }).addTo(m)
    tiles.current.bringToBack()
    try { localStorage.setItem('travel-map-base', base) } catch { /* a private window: just not remembered */ }
  }, [base])

  useEffect(() => {          // places, the route, photos
    const m = map.current
    const group = marks.current
    group.clearLayers()
    const located = places.filter((p) => p.lat != null && p.lon != null)
    if (route && located.length > 1) {
      const line = located.map((p) => [p.lat, p.lon])
      L.polyline(line, { color: '#ffffff', weight: 6, opacity: 0.8, interactive: false }).addTo(group)
      L.polyline(line, { color: colour('--tint'), weight: 3, dashArray: '6 6', interactive: false }).addTo(group)
    }
    located.forEach((p, i) => {
      const shown = p.shown ?? p.status
      const dot = route
        ? L.marker([p.lat, p.lon], { icon: L.divIcon({ className: 'travel-stop-pin', html: `<span>${i + 1}</span>`, iconSize: [24, 24] }),
          title: p.name, alt: p.name, keyboard: true })
        : L.circleMarker([p.lat, p.lon], { radius: 7, color: '#fff', weight: 2, fillColor: colour(TONES[shown] ?? '--tint'), fillOpacity: 1 })
      dot.bindTooltip(p.name).on('click', () => onPlace?.(p)).addTo(group)
    })
    for (const ph of photos) {
      if (ph.lat == null) continue
      const img = Object.assign(document.createElement('img'), { src: ph.url, alt: '' })
      L.marker([ph.lat, ph.lon], {
        icon: L.divIcon({ className: 'travel-photo-pin', html: img.outerHTML, iconSize: [38, 38], iconAnchor: [19, 44] }),
        title: ph.caption ?? 'Your photo', alt: ph.caption ?? 'Your photo', riseOnHover: true,
      }).on('click', () => onPhoto?.(ph)).addTo(group)
    }
    // Fit the map to what's on it when that changes (not on every re-render, or it'd jump back as you look around).
    const points = [...located.map((p) => [p.lat, p.lon]), ...photos.filter((p) => p.lat != null).map((p) => [p.lat, p.lon])]
    const key = points.map((p) => p.join(',')).join(';')
    if (key !== fitted.current) {
      fitted.current = key
      if (points.length === 1) m.setView(points[0], 10)
      else if (points.length > 1) m.fitBounds(L.latLngBounds(points), { padding: [28, 28], maxZoom: 12 })
    }
  }, [places, photos, route, onPlace, onPhoto])

  useEffect(() => {          // the spot just picked
    pin.current?.remove()
    pin.current = picked ? L.circleMarker([picked.lat, picked.lon], { radius: 9, color: '#fff', weight: 3,
      fillColor: colour('--out'), fillOpacity: 1, interactive: false }).addTo(map.current) : null
  }, [picked])

  return (
    <figure className={`travel-map-frame${picking ? ' picking' : ''}`}>
      <div className="segmented travel-map-bases" role="group" aria-label="Map">
        {Object.entries(BASES).map(([id, b]) => (
          <button key={id} type="button" aria-pressed={base === id} onClick={() => setBase(id)}>{b.label}</button>
        ))}
      </div>
      <div ref={box} className="travel-map-box" role="region" aria-label={label} />
      <figcaption className="travel-map-key">
        {legend ?? (route ? <span><i className="travel-key-stop" /> Stops, in order</span> : (
          <>
            <span><i className="travel-key-been" /> Been</span>
            <span><i className="travel-key-planned" /> Going</span>
            <span><i className="travel-key-want" /> Want to go</span>
          </>
        ))}
        {photos.some((p) => p.lat != null) && <span><i className="travel-key-photo" /> Your photo</span>}
        <span className="muted">{picking ? 'Tap the map where it is' : 'Zoom with + / −'}</span>
      </figcaption>
    </figure>
  )
}
