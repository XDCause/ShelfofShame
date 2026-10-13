// The Notion-style editor (BlockNote). Loaded only when a journal page opens (it's big), so the
// rest of the app stays quick.
//   /      menu of blocks: headings, lists, to-dos, quotes, images, tables...
//   @      mention a model, a supply or another page: a pill that opens it when clicked
//   photos dropped or pasted in are shrunk and stored by the API
import '@blocknote/mantine/style.css'
import { BlockNoteSchema, defaultInlineContentSpecs } from '@blocknote/core'
import { BlockNoteView } from '@blocknote/mantine'
import { createReactInlineContentSpec, SuggestionMenuController, useCreateBlockNote } from '@blocknote/react'
import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import { shrink } from '../../components/PhotoUpload.jsx'

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

const schema = BlockNoteSchema.create({
  inlineContentSpecs: { ...defaultInlineContentSpecs, mention: Mention },
})

const WHAT = { model: 'Model', supply: 'Supply', page: 'Journal page' }

// The editor follows the device's light / dark setting, like the rest of the app.
function useColourScheme() {
  const query = '(prefers-color-scheme: dark)'
  const [dark, setDark] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const media = window.matchMedia(query)
    const changed = (e) => setDark(e.matches)
    media.addEventListener('change', changed)
    return () => media.removeEventListener('change', changed)
  }, [])
  return dark ? 'dark' : 'light'
}

export default function Editor({ pageId, initialContent, onChange, onOpenMention }) {
  const theme = useColourScheme()
  const editor = useCreateBlockNote({
    schema,
    initialContent: initialContent?.length ? initialContent : undefined,
    uploadFile: async (file) => (await api.uploadJournalImage(await shrink(file, 1600), pageId)).url,
  })

  // What @ offers: models, supplies and pages matching what's typed after it.
  const mentionItems = async (query) => (await api.mentionable(query)).map((m) => ({
    title: m.label,
    subtext: WHAT[m.kind],
    group: WHAT[m.kind],
    onItemClick: () => editor.insertInlineContent([
      { type: 'mention', props: { kind: m.kind, ref: String(m.id), label: m.label } }, ' ',
    ]),
  }))

  return (
    <div className="journal-editor"
      onClick={(e) => {
        const pill = e.target.closest?.('.mention')
        if (pill) onOpenMention(pill.dataset.kind, Number(pill.dataset.ref))
      }}>
      <BlockNoteView editor={editor} theme={theme} onChange={() => onChange(editor.document)}>
        <SuggestionMenuController triggerCharacter="@" getItems={mentionItems} />
      </BlockNoteView>
    </div>
  )
}
