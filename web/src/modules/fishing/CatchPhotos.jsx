import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import PhotoPick from '../../components/PhotoPick.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'

// A catch's photos (api/app/fishing.py: POST /fishing/catches/{id}/photos, GET /fishing/photos/{id}, DELETE): thumbnails,
// add (camera / gallery: shrunk in the browser first, like hike photos), tap one to see it big (and delete it there).
// photos = [{photo_id, url}]; onChange(next list) after an add or a delete.
export function CatchPhotos({ catchId, photos = [], onChange }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [big, setBig] = useState(null)         // the photo shown large
  useEffect(() => {
    if (!big) return undefined
    const key = (e) => { if (e.key === 'Escape') setBig(null) }
    document.addEventListener('keydown', key)
    return () => document.removeEventListener('keydown', key)
  }, [big])

  const add = async (file) => {
    setBusy(true)
    setError('')
    try {
      const made = await api.addFishingPhoto(catchId, await shrink(file, 1600))
      onChange?.([...photos, made])
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }
  const remove = async (photo) => {
    setBusy(true)
    setError('')
    try {
      await api.deleteFishingPhoto(photo.photo_id)
      setBig(null)
      onChange?.(photos.filter((p) => p.photo_id !== photo.photo_id))
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }
  return (
    <div className="fst-photos">
      {photos.length > 0 && (
        <ul className="fst-thumbs" aria-label="Photos">
          {photos.map((p) => (
            <li key={p.photo_id}>
              <button type="button" className="fst-thumb" onClick={() => setBig(p)} aria-label="Show photo large">
                <img src={p.url} alt="Catch" loading="lazy" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {busy ? <span className="muted small">Saving...</span> : <PhotoPick onFile={add} label={photos.length ? 'Add another photo' : 'Add photo'} />}
      {error && <p className="alert error small" role="alert">{error}</p>}
      {big && (
        <div className="fst-lightbox" role="dialog" aria-modal="true" aria-label="Photo">
          <img src={big.url} alt="Catch, large" />
          <div className="fst-lightbox-bar">
            <button type="button" className="secondary" onClick={() => setBig(null)}>Close</button>
            <button type="button" className="plain destructive" onClick={() => remove(big)} disabled={busy}>Delete photo</button>
          </div>
        </div>
      )}
    </div>
  )
}
