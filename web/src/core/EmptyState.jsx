// A page with nothing on it yet: a soft icon, what goes here, and the button that adds the first
// one. (Searches and filters that find nothing say so in plain text instead.)
export default function EmptyState({ Icon, title, children, action, onAction }) {
  return (
    <div className="empty-state">
      {Icon && <span className="empty-icon" aria-hidden="true"><Icon size={30} /></span>}
      <h2 className="empty-title">{title}</h2>
      {children && <p className="muted">{children}</p>}
      {action && <button type="button" className="primary" onClick={onAction}>{action}</button>}
    </div>
  )
}
