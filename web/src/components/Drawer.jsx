import { useEffect, useId, useRef } from 'react'

// Open panels, newest last: Esc closes only the top one, and the page behind stays locked
// until the last one closes.
const open = []

// A panel over the page: from the right on wide screens, a sheet from the bottom on phones.
// Closes with Esc, the ✕, or a click on the dimmed background.
export default function Drawer({ title, onClose, children, footer, wide = false }) {
  const panel = useRef(null)
  const titleId = useId()
  // Parents pass a new onClose every render; keep the latest in a ref so the setup below runs
  // once (re-running it would pull focus away from whatever you're typing in).
  const close = useRef(onClose)
  close.current = onClose

  useEffect(() => {
    const me = {}
    open.push(me)
    const onKey = (e) => e.key === 'Escape' && open.at(-1) === me && close.current()
    document.addEventListener('keydown', onKey)
    document.body.classList.add('drawer-open') // stop the page behind from scrolling
    panel.current?.focus()
    return () => {
      open.splice(open.indexOf(me), 1)
      document.removeEventListener('keydown', onKey)
      if (open.length === 0) document.body.classList.remove('drawer-open')
    }
  }, [])

  return (
    <div className="drawer-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside className={wide ? 'drawer wide' : 'drawer'} role="dialog" aria-modal="true"
        aria-labelledby={titleId} ref={panel} tabIndex={-1}>
        <header className="drawer-head">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="icon-btn close" onClick={onClose} aria-label="Close">✕</button>
        </header>
        <div className="drawer-body">{children}</div>
        {footer && <footer className="drawer-foot">{footer}</footer>}
      </aside>
    </div>
  )
}
