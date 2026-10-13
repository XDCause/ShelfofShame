import { useRef, useState } from 'react'
import { readBarcode } from '../barcode.js'

// "Scan barcode" for any page: opens the phone camera, reads the barcode on the phone itself,
// and if the photo can't be read, offers a box to type the number instead.
// onBarcode(barcode, photo) does whatever the page needs (it may be async; errors it throws
// are shown here). `photo` is the picture taken, or null when the number was typed.
export default function ScanButton({ onBarcode, label = 'Scan barcode', className = 'primary' }) {
  const input = useRef(null)
  const [status, setStatus] = useState('') // '' | 'reading' | 'busy' | 'failed'
  const [photo, setPhoto] = useState(null)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState('')

  const handle = async (barcode, file) => {
    setStatus('busy')
    setError('')
    try {
      await onBarcode(barcode, file)
      setStatus('')
      setPhoto(null)
      setTyped('')
    } catch (e) {
      setPhoto(file)
      setError(e.message)
      setStatus('failed')
    }
  }

  const onPhoto = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // so the same file can be chosen again
    if (!file) return
    setStatus('reading')
    setError('')
    let barcode = null
    try {
      barcode = await readBarcode(file)
    } catch {
      // treated as "no barcode found"
    }
    if (barcode) return handle(barcode, file)
    setPhoto(file)
    setError("Couldn't find a barcode in that photo. Try closer, square-on and in good light, or type the number under the bars.")
    setStatus('failed')
  }

  const cancel = () => {
    setStatus('')
    setPhoto(null)
    setError('')
  }

  return (
    <div className="scan-control">
      {/* capture="environment" = open the back camera straight away on phones */}
      <input ref={input} type="file" accept="image/*" capture="environment" onChange={onPhoto} hidden />
      <button type="button" className={className} onClick={() => input.current.click()}
        disabled={status === 'reading' || status === 'busy'}>
        {status === 'reading' ? 'Reading barcode...' : status === 'busy' ? 'Looking up...' : label}
      </button>
      {status !== 'failed' && (
        <button type="button" className="plain" onClick={() => setStatus('failed')}>Type a barcode</button>
      )}

      {status === 'failed' && (
        <div className="scan-panel">
          {error && <p className="alert low small">{error}</p>}
          {/* A div, not a <form>: this control is also used inside the supply form, and forms
              can't be nested (the inner submit would submit the whole supply form). */}
          <div className="lookup-row">
            <input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  if (typed.trim()) handle(typed.trim(), photo)
                }
              }}
              inputMode="numeric"
              placeholder="e.g. 4950344070053"
              aria-label="Barcode number"
              autoFocus
            />
            <button type="button" className="primary" disabled={!typed.trim()}
              onClick={() => handle(typed.trim(), photo)}>Look up</button>
            <button type="button" className="plain" onClick={cancel}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}
