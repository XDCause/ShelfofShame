import { useState } from 'react'
import { PenIcon } from '../../components/icons.jsx'

// Handwriting into a journal page. Samsung's "S Pen to text" (and other tablets' handwriting
// keyboards) turn handwriting into typed text as you write - but only in plain text boxes, not in
// the rich-text editor. This is a plain text box at the foot of the page: write in it, and each
// line moves into the page when you start a new one (or tap Add, or leave the box).
// onAdd(lines) adds the lines to the end of the page as paragraphs.
export default function PenBox({ onAdd, onClose }) {
  const [text, setText] = useState('')

  const add = (value = text) => {
    const lines = value.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lines.length) onAdd(lines)
    setText('')
  }

  // A new line (Enter, or the handwriting keyboard's own new line) moves what's finished.
  const change = (e) => {
    const value = e.target.value
    if (value.includes('\n')) {
      const finished = value.slice(0, value.lastIndexOf('\n'))
      add(finished)
      setText(value.slice(value.lastIndexOf('\n') + 1))
    } else {
      setText(value)
    }
  }

  return (
    <div className="pen-box" role="group" aria-label="Pen box">
      <PenIcon size={20} />
      <textarea rows={2} value={text} onChange={change} onBlur={() => add()}
        placeholder="Write here with your pen - it turns into text. A new line adds it to the page."
        aria-label="Pen box: handwriting turns into text" />
      <div className="pen-box-actions">
        <button type="button" className="primary" onMouseDown={(e) => e.preventDefault()} onClick={() => add()}
          disabled={!text.trim()}>Add</button>
        <button type="button" className="plain" onMouseDown={(e) => e.preventDefault()}
          onClick={() => { add(); onClose() }}>Close</button>
      </div>
    </div>
  )
}
