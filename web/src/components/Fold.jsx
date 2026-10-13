import { useState } from 'react'

// A section that's closed until you tap its heading (Settings, and long lists in panels).
// Its content is only created when it's first opened, so closed sections don't load anything.
export default function Fold({ title, detail, children, open: startOpen = false, className = '' }) {
  const [opened, setOpened] = useState(startOpen)
  return (
    <details className={`fold ${className}`} open={startOpen}
      onToggle={(e) => e.currentTarget.open && setOpened(true)}>
      <summary>
        <span className="fold-title">{title}</span>
        {detail != null && <span className="fold-detail">{detail}</span>}
      </summary>
      {opened && <div className="fold-body">{children}</div>}
    </details>
  )
}
