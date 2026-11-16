import { useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { useApp } from '../app-context.js'

// Two helpers above a journal page's text (the editor is passed in):
//   Speak      the browser's speech recognition types what you say at the cursor (English, Australian). Hidden where the
//              browser doesn't have it. Nothing is recorded or kept by this app; Chrome and Edge do the listening on
//              their own makers' servers, which is why it says so on hover.
//   Your day   puts a short summary of that day (calendar events, plays, hikes, sessions, games, photos, to-dos done)
//              under the cursor (api/app/journal_day.py); you write around it.
const Recognition = typeof window !== 'undefined' ? window.SpeechRecognition ?? window.webkitSpeechRecognition : undefined

// What the browser heard, ready to type: trimmed, with a space after.
export const heard = (text) => `${text.trim()} `

export default function JournalTools({ editor, day }) {
  const { showToast } = useApp()
  const [listening, setListening] = useState(false)
  const rec = useRef(null)
  const wanted = useRef(false)          // you haven't pressed stop: restart when the browser ends a quiet spell

  const stop = () => {
    wanted.current = false
    rec.current?.stop()
    setListening(false)
  }
  useEffect(() => () => { wanted.current = false; rec.current?.abort() }, [])

  const speak = () => {
    if (listening) { stop(); return }
    const r = new Recognition()
    r.lang = 'en-AU'
    r.continuous = true
    r.interimResults = false
    r.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i += 1) {
        if (!e.results[i].isFinal) continue
        const text = e.results[i][0].transcript
        if (text.trim()) {
          try { editor.insertInlineContent(heard(text)) } catch { showToast("Couldn't type that - click in the page first.") }
        }
      }
    }
    r.onerror = (e) => {
      if (e.error === 'no-speech' || e.error === 'aborted') return
      wanted.current = false
      setListening(false)
      showToast(e.error === 'not-allowed' ? 'Allow the microphone to dictate.' : `Dictation stopped (${e.error}).`)
    }
    r.onend = () => {
      if (wanted.current) { try { r.start() } catch { setListening(false) } } else setListening(false)
    }
    rec.current = r
    wanted.current = true
    try { r.start(); setListening(true) } catch { wanted.current = false }
  }

  const yourDay = async () => {
    try {
      const d = await api.daySummary(day)
      if (!d.lines.length) { showToast('Nothing logged for that day.'); return }
      editor.insertBlocks(d.blocks, editor.getTextCursorPosition().block, 'after')
    } catch (e) {
      showToast(e.message)
    }
  }

  return (
    <div className="journal-tools" role="group" aria-label="Page tools">
      {Recognition && (
        <button type="button" className={listening ? 'secondary journal-tool-on' : 'plain'} aria-pressed={listening}
          onMouseDown={(e) => e.preventDefault()} onClick={speak}
          title="Type what you say at the cursor. Your browser does the listening (Chrome and Edge use their own servers); nothing is recorded here.">
          {listening ? '● Listening - tap to stop' : '🎤 Speak'}</button>
      )}
      <button type="button" className="plain" onMouseDown={(e) => e.preventDefault()} onClick={yourDay}
        title="Add that day's events, plays, hikes, photos and to-dos done to the page">Your day</button>
    </div>
  )
}
