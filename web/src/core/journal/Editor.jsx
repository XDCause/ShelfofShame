// The Notion-style editor (BlockNote). Loaded only when a journal page opens (it's big), so the
// rest of the app stays quick.
//   /      menu of blocks: headings, lists, to-dos, quotes, images, tables... and Drawing (a pen
//          sketch: a preview in the page, tapped to open the canvas)
//   @      mention a model, a supply, a board game, gear or another page: a pill that opens it
//   photos dropped or pasted in are shrunk and stored by the API
import '@blocknote/mantine/style.css'
import {
  BlockNoteSchema, defaultBlockSpecs, defaultInlineContentSpecs, filterSuggestionItems, insertOrUpdateBlockForSlashMenu,
} from '@blocknote/core'
import { BlockNoteView } from '@blocknote/mantine'
import {
  createReactBlockSpec, createReactInlineContentSpec, getDefaultReactSlashMenuItems, SuggestionMenuController,
  useCreateBlockNote,
} from '@blocknote/react'
import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../../api.js'
import { PenIcon } from '../../components/icons.jsx'
import { shrink } from '../../components/PhotoUpload.jsx'
import { useTheme } from '../theme.js'

// A mention is stored in the page as {type: "mention", props: {kind, ref, label}}; the API reads
// them on save to link the page to what it mentions (api/app/journal.py).
const Mention = createReactInlineContentSpec(
  {
    type: 'mention',
    propSchema: { kind: { default: 'page' }, ref: { default: '' }, label: { default: '' } },
    content: 'none',
  },
  {
    render: ({ inlineContent: { props } }) => (
      <span className={`mention mention-${props.kind}`} data-kind={props.kind} data-ref={props.ref}
        title={`Open ${props.label}`}>@{props.label}</span>
    ),
  },
)

// What the page knows about its drawings: their preview addresses, and how to open one.
const Drawings = createContext({ previews: {}, open: () => {} })

// A drawing is stored in the page as {type: "drawing", props: {drawingId}}; the drawing itself
// (strokes, pictures, preview) is in journal_drawings (api/app/journal_drawings.py).
const DrawingBlock = createReactBlockSpec(
  { type: 'drawing', propSchema: { drawingId: { default: '' } }, content: 'none' },
  { render: ({ block }) => <DrawingPreview id={block.props.drawingId} /> },
)

function DrawingPreview({ id }) {
  const { previews, open } = useContext(Drawings)
  const [failed, setFailed] = useState(false)
  const url = previews[id]
  return (
    <button type="button" className="drawing-block" contentEditable={false} onClick={() => open(Number(id))}
      aria-label="Open the drawing">
      {url && !failed ? <img src={url} alt="A drawing" onError={() => setFailed(true)} />
        : <span className="drawing-empty"><PenIcon size={28} /> Tap to draw</span>}
    </button>
  )
}

const schema = BlockNoteSchema.create({
  blockSpecs: { ...defaultBlockSpecs, drawing: DrawingBlock() },
  inlineContentSpecs: { ...defaultInlineContentSpecs, mention: Mention },
})

const WHAT = { model: 'Model', supply: 'Supply', page: 'Journal page', game: 'Board game', gear: 'Gear' }

// previews: {drawingId: preview URL}; onDraw(id) opens the canvas for a drawing.
// onReady(editor) hands the page the editor, e.g. so the pen box can add text to it.
export default function Editor({ pageId, initialContent, onChange, onOpenMention, previews = {}, onDraw, onReady }) {
  const theme = useTheme() // light / dark, like the rest of the app
  const editor = useCreateBlockNote({
    schema,
    initialContent: initialContent?.length ? initialContent : undefined,
    uploadFile: async (file) => (await api.uploadJournalImage(await shrink(file, 1600), pageId)).url,
  })

  useEffect(() => { onReady?.(editor) }, [editor, onReady])

  // What @ offers: models, supplies, pages, games and gear matching what's typed after it.
  const mentionItems = async (query) => (await api.mentionable(query)).map((m) => ({
    title: m.label,
    subtext: WHAT[m.kind],
    group: WHAT[m.kind],
    onItemClick: () => editor.insertInlineContent([
      { type: 'mention', props: { kind: m.kind, ref: String(m.id), label: m.label } }, ' ',
    ]),
  }))

  // The / menu: BlockNote's own blocks, plus Drawing.
  const drawing = {
    title: 'Drawing',
    subtext: 'Sketch with a pen, finger or mouse',
    aliases: ['draw', 'sketch', 'pen', 'whiteboard', 'canvas'],
    group: 'Drawing',
    icon: <PenIcon size={18} />,
    onItemClick: async () => {
      const made = await api.addDrawing(pageId)
      insertOrUpdateBlockForSlashMenu(editor, { type: 'drawing', props: { drawingId: String(made.drawing_id) } })
      onDraw(made.drawing_id)
    },
  }
  const slashItems = async (query) =>
    filterSuggestionItems([...getDefaultReactSlashMenuItems(editor), drawing], query)

  return (
    <Drawings.Provider value={{ previews, open: onDraw }}>
      <div className="journal-editor"
        onClick={(e) => {
          const pill = e.target.closest?.('.mention')
          if (pill) onOpenMention(pill.dataset.kind, Number(pill.dataset.ref))
        }}>
        <BlockNoteView editor={editor} theme={theme} onChange={() => onChange(editor.document)} slashMenu={false}>
          <SuggestionMenuController triggerCharacter="/" getItems={slashItems} />
          <SuggestionMenuController triggerCharacter="@" getItems={mentionItems} />
        </BlockNoteView>
      </div>
    </Drawings.Provider>
  )
}
