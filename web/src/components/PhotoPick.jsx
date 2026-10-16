import { useRef, useState } from 'react'
import { photoFromUrl } from '../api.js'

// "Add photo" anywhere a photo can be added (build log, product photos, board games, gear).
// On a phone or tablet (a touch screen) it's two buttons: Take photo (opens the camera straight
// away) and Gallery - because newer Android versions open only the gallery for a plain photo
// picker, with no way to the camera. On a computer it's one button that opens the file picker.
// onFile(file) gets the picture chosen - or, with `multiple`, a list of them (the gallery lets you
// pick several; the camera takes one each time, so press it again for more).
// Photos also have "Paste or link": a picture copied in the browser ("Copy image") or a screenshot,
// pasted with Ctrl+V (or dropped on the box), or a picture's web address - fetched by the API, since
// a page can't download pictures from other sites itself (api/app/webphoto.py).
const touch = typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches

// For videos: accept="video/*" with cameraLabel "Record video" and galleryLabel "Choose video".
export default function PhotoPick({ onFile, label = 'Add photo', className = 'secondary', disabled = false, multiple = false,
  accept = 'image/*', cameraLabel = 'Take photo', galleryLabel = 'Gallery' }) {
  const camera = useRef(null)
  const gallery = useRef(null)
  const [pasting, setPasting] = useState(false)
  const give = (files) => files.length && onFile(multiple ? files : files[0])
  const pick = (e) => {
    const files = [...(e.target.files ?? [])]
    e.target.value = '' // so the same picture can be chosen again
    give(files)
  }
  const photos = accept.startsWith('image')
  const pasteButton = photos && (
    <button type="button" className={className} onClick={() => setPasting(!pasting)} disabled={disabled}
      aria-expanded={pasting}>{touch ? 'Link' : 'Paste or link'}</button>
  )
  return (
    <span className="photo-pick-wrap">
      <input ref={camera} type="file" accept={accept} capture="environment" onChange={pick} hidden data-source="camera" />
      <input ref={gallery} type="file" accept={accept} onChange={pick} hidden data-source="gallery" multiple={multiple} />
      {touch ? (
        <span className="photo-pick" role="group" aria-label={label}>
          <button type="button" className={className} onClick={() => camera.current.click()} disabled={disabled}>{cameraLabel}</button>
          <button type="button" className={className} onClick={() => gallery.current.click()} disabled={disabled}>{galleryLabel}</button>
          {pasteButton}
        </span>
      ) : photos ? (
        <span className="photo-pick" role="group" aria-label={label}>
          <button type="button" className={className} onClick={() => gallery.current.click()} disabled={disabled}>{label}</button>
          {pasteButton}
        </span>
      ) : (
        <button type="button" className={className} onClick={() => gallery.current.click()} disabled={disabled}>{label}</button>
      )}
      {pasting && <PasteBox onFile={(f) => { setPasting(false); give([f]) }} onCancel={() => setPasting(false)} />}
    </span>
  )
}

// A data: address (some image searches copy these) -> a File, without fetching anything.
function fromDataUrl(url) {
  const [head, data] = url.split(',', 2)
  const type = head.match(/^data:(image\/(?:jpeg|png|webp|gif));base64$/)?.[1]
  if (!type || !data) throw new Error('That pasted picture is an unusual type: try saving it and adding it instead.')
  const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0))
  return new File([bytes], 'pasted', { type })
}

// The paste / link box: Ctrl+V a picture, drop one on it, or paste (or type) its web address.
function PasteBox({ onFile, onCancel }) {
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const imageIn = (items) => [...(items ?? [])].find((i) => i.kind === 'file' && i.type.startsWith('image/'))?.getAsFile()
  const fetchUrl = async (address) => {
    const text = address.trim()
    if (!text) return
    setError('')
    if (text.startsWith('data:')) {
      try { onFile(fromDataUrl(text)) } catch (e) { setError(e.message) }
      return
    }
    setBusy(true)
    try {
      const blob = await photoFromUrl(text)
      onFile(new File([blob], 'from-the-web', { type: blob.type }))
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  const onPaste = (e) => {
    const file = imageIn(e.clipboardData?.items)
    if (file) { e.preventDefault(); onFile(file); return }
    const text = e.clipboardData?.getData('text/plain')?.trim()
    if (text && /^(https?:\/\/|data:image\/)/i.test(text)) {
      e.preventDefault()
      setUrl(text.startsWith('data:') ? '' : text)
      fetchUrl(text)
    }
  }
  const onDrop = (e) => {
    e.preventDefault()
    const file = [...(e.dataTransfer?.files ?? [])].find((f) => f.type.startsWith('image/'))
    if (file) { onFile(file); return }
    const link = e.dataTransfer?.getData('text/uri-list')?.split('\n').find((l) => l && !l.startsWith('#'))
      || e.dataTransfer?.getData('text/plain')
    if (link) { setUrl(link.trim()); fetchUrl(link) }
  }
  const keys = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); fetchUrl(url) }
    if (e.key === 'Escape') { e.stopPropagation(); onCancel() }
  }
  return (
    <span className="paste-box" onDragOver={(e) => e.preventDefault()} onDrop={onDrop}>
      <span className="paste-row">
        <input value={url} onChange={(e) => setUrl(e.target.value)} onPaste={onPaste} onKeyDown={keys} autoFocus disabled={busy}
          placeholder={touch ? "The picture's web address" : 'Ctrl+V a picture, or its web address'}
          aria-label="Paste a picture or its web address" />
        <button type="button" className="primary small" disabled={busy || !url.trim()} onClick={() => fetchUrl(url)}>
          {busy ? 'Getting it...' : 'Use'}</button>
        <button type="button" className="plain small" onClick={onCancel}>Cancel</button>
      </span>
      <span className="hint">{touch ? 'Long-press a picture on a web page, Copy image address, then paste it here.'
        : 'Right-click a picture on a web page: Copy image (then Ctrl+V here) or Copy image address. You can also drag it here.'}</span>
      {error && <span className="alert error small">{error}</span>}
    </span>
  )
}
