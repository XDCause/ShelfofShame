import { useEffect, useState } from 'react'
import { api } from '../../api.js'

// Tags as removable chips, plus a box to add one (Enter or comma), suggesting tags already used.
export default function TagsInput({ tags, onChange }) {
  const [draft, setDraft] = useState('')
  const [known, setKnown] = useState([])
  useEffect(() => { api.journalTags().then((t) => setKnown(t.map((x) => x.name))).catch(() => {}) }, [])

  const add = (text = draft) => {
    const name = text.replace(/,$/, '').trim()
    setDraft('')
    if (name && !tags.some((t) => t.toLowerCase() === name.toLowerCase())) onChange([...tags, name])
  }

  return (
    <div className="tags-input">
      {tags.map((t) => (
        <span key={t} className="chip tag-chip">#{t}
          <button type="button" aria-label={`Remove tag ${t}`} onClick={() => onChange(tags.filter((x) => x !== t))}>✕</button>
        </span>
      ))}
      <input value={draft} list="journal-tags" placeholder="+ Tag" aria-label="Add a tag"
        onChange={(e) => (e.target.value.endsWith(',') ? add(e.target.value) : setDraft(e.target.value))}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
        onBlur={() => add()} />
      <datalist id="journal-tags">{known.filter((k) => !tags.includes(k)).map((k) => <option key={k} value={k} />)}</datalist>
    </div>
  )
}
