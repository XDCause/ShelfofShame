import { useRef } from 'react'

// "Add photo" anywhere a photo can be added (build log, product photos, board games, gear).
// On a phone or tablet (a touch screen) it's two buttons: Take photo (opens the camera straight
// away) and Gallery - because newer Android versions open only the gallery for a plain photo
// picker, with no way to the camera. On a computer it's one button that opens the file picker.
// onFile(file) gets the picture chosen.
const touch = typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches

export default function PhotoPick({ onFile, label = 'Add photo', className = 'secondary', disabled = false }) {
  const camera = useRef(null)
  const gallery = useRef(null)
  const pick = (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // so the same picture can be chosen again
    if (file) onFile(file)
  }
  return (
    <>
      <input ref={camera} type="file" accept="image/*" capture="environment" onChange={pick} hidden data-source="camera" />
      <input ref={gallery} type="file" accept="image/*" onChange={pick} hidden data-source="gallery" />
      {touch ? (
        <span className="photo-pick" role="group" aria-label={label}>
          <button type="button" className={className} onClick={() => camera.current.click()} disabled={disabled}>Take photo</button>
          <button type="button" className={className} onClick={() => gallery.current.click()} disabled={disabled}>Gallery</button>
        </span>
      ) : (
        <button type="button" className={className} onClick={() => gallery.current.click()} disabled={disabled}>{label}</button>
      )}
    </>
  )
}
