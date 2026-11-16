import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'

// Every track of a year on one map. Each is drawn thin and see-through, so the paths you walk again and again
// build up darker: a heatmap made of your own lines. Tiles: OpenTopoMap (the same map as a hike's), credit in the corner.
export default function YearMap({ tracks, label }) {
  const box = useRef(null)
  useEffect(() => {
    const m = L.map(box.current, { scrollWheelZoom: false, zoomSnap: 0.25 })
    L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      subdomains: 'abc', maxZoom: 17, referrerPolicy: 'strict-origin-when-cross-origin',
      attribution: 'Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM · '
        + 'Style © <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)',
    }).addTo(m)
    const all = []
    for (const t of tracks) {
      L.polyline(t.points, { color: '#d9480f', weight: 5, opacity: 0.28, interactive: false, lineCap: 'round', lineJoin: 'round' }).addTo(m)
      all.push(...t.points)
    }
    if (all.length) m.fitBounds(L.latLngBounds(all), { padding: [24, 24], maxZoom: 15 })
    else m.setView([0, 0], 2)
    return () => { m.remove() }
  }, [tracks])
  return <div ref={box} className="hike-year-map" role="region" aria-label={label} />
}
