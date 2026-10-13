import { useEffect } from 'react'

// A message bar across the page ("Added to inventory: ...") with a ✕ to close it.
// Good news (type "ok") also goes away by itself after a few seconds; warnings and errors stay
// until you close them.
export default function Notice({ type, children, onClose }) {
  useEffect(() => {
    if (type !== 'ok') return undefined
    const t = setTimeout(onClose, 8000)
    return () => clearTimeout(t)
  }, [type, children, onClose])

  return (
    <p className={`alert notice ${type}`} role="status">
      <span>{children}</span>
      <button type="button" className="notice-close" aria-label="Close message" onClick={onClose}>✕</button>
    </p>
  )
}
