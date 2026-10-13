import { useRef, useState } from 'react'
import { api } from '../api.js'

// Phone photos are often 3-5 MB. Shrink to at most 1000 px in the browser and save as JPEG
// (~100-200 KB), so the database and its backups stay small. The white fill stops transparent
// PNG areas turning black, since JPEG has no transparency.
export async function shrink(file, maxSide = 1000) {
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    return blob && blob.size < file.size ? blob : file
  } catch {
    return file // browser couldn't decode it here; let the server judge the original
  }
}

// "Upload photo" / "Remove photo" for one brand + product code. Works for any brand.
// On a phone, the file picker offers the camera as well as the photo library.
export default function PhotoUpload({ brandId, productCode, hasPhoto, onChanged }) {
  const input = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!brandId || !productCode) {
    return <p className="hint">Set a brand and product code to add a photo.</p>
  }

  const pick = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // so choosing the same file again still triggers a change
    if (!file) return
    setBusy(true)
    setError('')
    try {
      await api.uploadPhoto(brandId, productCode, await shrink(file))
      onChanged('Photo saved.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    setError('')
    try {
      await api.deletePhoto(brandId, productCode)
      onChanged('Photo removed.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="photo-upload">
      <input ref={input} type="file" accept="image/*" onChange={pick} hidden />
      <button type="button" className="secondary" onClick={() => input.current.click()} disabled={busy}>
        {busy ? 'Saving...' : hasPhoto ? 'Replace photo' : 'Upload photo'}
      </button>
      {hasPhoto && (
        <button type="button" className="plain destructive" onClick={remove} disabled={busy}>Remove photo</button>
      )}
      {error && <p className="alert error small">{error}</p>}
    </div>
  )
}
