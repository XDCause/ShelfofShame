import { useRef, useState } from 'react'
import { findGrid, greyOf, readGrid } from './photoRead.js'

// "Read a photo": take or pick a photo of a paper's grid, fit its four corners, read the digits onto the type-in board.
export default function PhotoReader({ onRead }) {
  const [photo, setPhoto] = useState(null)          // {url, grey: {g, w, h}}
  const [corners, setCorners] = useState(null)
  const [message, setMessage] = useState('')
  const drag = useRef(null)
  const box = useRef(null)
  const pick = (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      const grey = greyOf(img)
      setPhoto({ url, grey })
      setCorners(findGrid(grey))
      setMessage('Drag the corners onto the grid\'s outer corners if they\'re off, then read it.')
    }
    img.onerror = () => setMessage("That photo couldn't be opened.")
    img.src = url
  }
  const move = (e) => {
    if (drag.current == null || !photo) return
    const r = box.current.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * photo.grey.w, y = ((e.clientY - r.top) / r.height) * photo.grey.h
    setCorners((cs) => cs.map((p, i) => (i === drag.current ? [Math.max(0, Math.min(photo.grey.w, x)), Math.max(0, Math.min(photo.grey.h, y))] : p)))
  }
  const read = () => {
    const grid = readGrid(photo.grey, corners)
    const n = grid.filter(Boolean).length
    onRead(grid)
    setMessage(`Read ${n} clues. Check every one against the paper before you play - photos can fool it (a smudge, a fold, an odd typeface).`)
  }
  return (
    <div className="sdk-photo">
      <label className="button secondary small">📷 Read a photo of the grid
        <input type="file" accept="image/*" onChange={pick} hidden aria-label="Photo of the grid" /></label>
      {photo && (
        <>
          <div className="sdk-photo-box" ref={box} onPointerMove={move} onPointerUp={() => { drag.current = null }} onPointerLeave={() => { drag.current = null }}>
            <img src={photo.url} alt="The photo of the grid" />
            <svg viewBox={`0 0 ${photo.grey.w} ${photo.grey.h}`} preserveAspectRatio="none" aria-hidden="true">
              <polygon points={corners.map((p) => p.join(',')).join(' ')} />
              {corners.map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={Math.max(photo.grey.w, photo.grey.h) * 0.022}
                  onPointerDown={(e) => { e.preventDefault(); drag.current = i; e.currentTarget.setPointerCapture?.(e.pointerId) }} />
              ))}
            </svg>
          </div>
          <div className="button-row">
            <button type="button" className="primary small" onClick={read}>Read the digits</button>
            <button type="button" className="plain small" onClick={() => { setPhoto(null); setMessage('') }}>Close the photo</button>
          </div>
        </>
      )}
      {message && <p className="muted small">{message}</p>}
    </div>
  )
}
