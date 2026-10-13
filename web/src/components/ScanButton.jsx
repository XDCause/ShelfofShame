import { useRef, useState } from 'react'
import { readBarcode } from '../barcode.js'

// "Use barcode" for any page. One button that offers the two ways in:
//   Scan with camera   opens the phone camera; the barcode is read on the phone itself
//   Type the number    a box for the digits under the bars
// If a photo can't be read, the typing box opens with a hint.
// onBarcode(barcode, photo) does whatever the page needs (it may be async; errors it throws
// are shown here). `photo` is the picture taken, or null when the number was typed.
export default function ScanButton({ onBarcode, label = 'Use barcode', className = 'secondary' }) {
  const input = useRef(null)
  const [status, setStatus] = useState('') // '' | 'choose' | 'reading' | 'busy' | 'typing'
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
      setStatus('typing')
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
    setStatus('typing')
  }

  const cancel = () => {
    setStatus('')
    setPhoto(null)
    setError('')
  }

  const working = status === 'reading' || status === 'busy'
  return (
    <div className="scan-control">
      {/* capture="environment" = open the back camera straight away on phones */}
      <input ref={input} type="file" accept="image/*" capture="environment" onChange={onPhoto} hidden />
      {status !== 'typing' && (
        <button type="button" className={className} aria-expanded={status === 'choose'} disabled={working}
          onClick={() => setStatus(status === 'choose' ? '' : 'choose')}>
          {status === 'reading' ? 'Reading barcode...' : status === 'busy' ? 'Looking up...' : label}
        </button>
      )}
      {status === 'choose' && (
        <span className="scan-choices" role="group" aria-label="Use barcode">
          <button type="button" className="plain" onClick={() => input.current.click()}>Scan with camera</button>
          <button type="button" className="plain" onClick={() => setStatus('typing')}>Type the number</button>
        </span>
      )}

      {status === 'typing' && (
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
