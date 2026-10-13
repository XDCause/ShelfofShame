// The drawing canvas (Excalidraw): pen strokes with pressure, shapes, arrows, text, pictures, on
// an endless page you can pan and zoom. Loaded only when a drawing opens (it's big).
//   overlay   full screen over the app, with Done (a sketch in a notes page, or "Full screen")
//   embedded  inside a whiteboard page, with Full screen (onExpand)
// With a pen (an S Pen on a Galaxy Tab), Excalidraw switches to pen mode by itself: the pen
// draws and fingers pan and zoom, so a resting palm doesn't scribble.
// It saves by itself a moment after you stop: the strokes, any new pictures (each sent once),
// and now and then a PNG preview for the page and the journal list.
import '@excalidraw/excalidraw/index.css'
import { Excalidraw, exportToBlob, getSceneVersion, MainMenu } from '@excalidraw/excalidraw'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api.js'
import { useTheme } from '../theme.js'

const SAVE_AFTER_MS = 1200      // after the last stroke
const PREVIEW_EVERY_MS = 10000  // a fresh preview at most this often while drawing (and on close)

export default function DrawingCanvas({ drawingId, overlay = false, title = 'Drawing', onClose, onExpand, onSaved }) {
  const theme = useTheme()
  const [initial, setInitial] = useState(null)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')          // '', 'saving', 'saved'
  const canvas = useRef(null)                        // Excalidraw's API
  // The latest scene, copied on every change. Saves use this copy, never the canvas itself: by the
  // time a closing canvas makes its last save, Excalidraw has already emptied it (that once saved
  // a blank board over the drawing).
  const latest = useRef(null)                        // {elements, appState, files}
  const saved = useRef({ version: null, files: new Set(), previewAt: 0, previewDirty: false })
  const queue = useRef(Promise.resolve())            // one save at a time, in order
  const timer = useRef(null)

  useEffect(() => {
    let current = true
    api.getDrawing(drawingId).then((d) => {
      if (!current) return
      const elements = d.scene.elements ?? []
      saved.current = { version: getSceneVersion(elements), files: new Set(Object.keys(d.files ?? {})),
        previewAt: 0, previewDirty: !d.preview_url && elements.length > 0 }
      latest.current = null                          // nothing drawn here yet
      setInitial({ elements, appState: d.scene.appState ?? {}, files: d.files ?? {}, scrollToContent: true })
    }).catch((e) => setError(e.message))
    return () => { current = false }
  }, [drawingId])

  // Save what changed since last time. preview = also make a new PNG if the drawing changed.
  const save = useCallback((preview = false) => {
    queue.current = queue.current.then(async () => {
      if (!latest.current) return                    // no change since it opened
      const { elements, appState, files } = latest.current
      const version = getSceneVersion(elements)
      const fresh = Object.entries(files)
        .filter(([id]) => !saved.current.files.has(id) && elements.some((e) => e.fileId === id))
      const changedScene = version !== saved.current.version
      const wantPreview = preview && (saved.current.previewDirty || changedScene) && elements.length > 0
      if (!changedScene && !fresh.length && !wantPreview) return
      setStatus('saving')
      try {
        if (fresh.length) {
          await api.addDrawingFiles(drawingId, Object.fromEntries(
            fresh.map(([id, f]) => [id, { mimeType: f.mimeType, dataURL: f.dataURL }])))
          fresh.forEach(([id]) => saved.current.files.add(id))
        }
        let meta = null
        if (changedScene) {
          meta = await api.saveDrawing(drawingId, {
            elements,
            app_state: { viewBackgroundColor: appState.viewBackgroundColor, gridModeEnabled: appState.gridModeEnabled },
          })
          saved.current.version = version
          saved.current.previewDirty = true
        }
        if (wantPreview) {
          const blob = await exportToBlob({
            elements, files, mimeType: 'image/png', maxWidthOrHeight: 1400, exportPadding: 24,
            appState: { ...appState, exportBackground: true, exportWithDarkMode: false },
          })
          meta = await api.saveDrawingPreview(drawingId, blob)
          saved.current.previewAt = Date.now()
          saved.current.previewDirty = false
        }
        setStatus('saved')
        if (meta) onSaved?.(meta)
      } catch (e) {
        setError(`Couldn't save the drawing: ${e.message}`)
        setStatus('')
      }
    })
    return queue.current
  }, [drawingId, onSaved])

  // Every change (even moving the pointer) comes here: keep a copy, save once things go quiet.
  const onChange = useCallback((elements, appState, files) => {
    latest.current = { elements: elements.filter((e) => !e.isDeleted), appState, files }
    clearTimeout(timer.current)
    timer.current = setTimeout(() => save(Date.now() - saved.current.previewAt > PREVIEW_EVERY_MS), SAVE_AFTER_MS)
  }, [save])

  // Leaving (Done, another page, switching apps on the tablet): save now, with a preview.
  useEffect(() => {
    const away = () => { if (document.visibilityState === 'hidden') save(true) }
    document.addEventListener('visibilitychange', away)
    return () => {
      document.removeEventListener('visibilitychange', away)
      clearTimeout(timer.current)
      save(true)
    }
  }, [save])

  // Done (or Full screen): save first, so the next view opens with everything in it.
  const leave = (then) => async () => {
    clearTimeout(timer.current)
    await save(true)
    then()
  }

  // Like a notebook: it always opens with the pen picked up, ready to write.
  const ready = (ex) => {
    canvas.current = ex
    if (ex) setTimeout(() => ex.setActiveTool({ type: 'freedraw' }))
  }

  return (
    <div className={overlay ? 'drawing-overlay' : 'drawing-embedded'} data-testid="drawing-canvas">
      <div className="drawing-bar">
        <strong className="drawing-title">{title}</strong>
        <span className="muted small" role="status" aria-live="polite">
          {status === 'saving' ? 'Saving...' : status === 'saved' ? 'Saved' : ''}
        </span>
        <span className="spacer" />
        {onExpand && <button type="button" className="secondary" onClick={leave(onExpand)}>Full screen</button>}
        {onClose && <button type="button" className="primary" onClick={leave(onClose)}>Done</button>}
      </div>
      {error && <p className="alert error small">{error}</p>}
      <div className="drawing-surface">
        {!initial ? <p className="muted loading">Opening the canvas...</p> : (
          <Excalidraw initialData={initial} excalidrawAPI={ready} onChange={onChange} theme={theme} name={title}
            UIOptions={{ canvasActions: { loadScene: false, saveToActiveFile: false, export: false, toggleTheme: false } }}>
            <MainMenu>
              <MainMenu.DefaultItems.SaveAsImage />
              <MainMenu.DefaultItems.ClearCanvas />
              <MainMenu.DefaultItems.Help />
              <MainMenu.Separator />
              <MainMenu.DefaultItems.ChangeCanvasBackground />
            </MainMenu>
          </Excalidraw>
        )}
      </div>
    </div>
  )
}
