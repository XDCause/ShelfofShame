-- Drawing in the journal, with a pen (2026-10-14).
--
--   journal_pages.kind  'notes' (blocks, like Notion) or 'whiteboard' (the whole page is one
--                       infinite canvas, like a reMarkable notebook or a whiteboard)
--   journal_drawings    a canvas (Excalidraw): its shapes and pen strokes (scene), the pictures
--                       dropped onto it (files), a PNG preview for lists and the page, and the
--                       words typed on it (text, for search). A notes page has one per Drawing
--                       block; a whiteboard page has exactly one (board = true).
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'notes';
ALTER TABLE journal_pages DROP CONSTRAINT IF EXISTS journal_pages_kind_check;
ALTER TABLE journal_pages ADD CONSTRAINT journal_pages_kind_check CHECK (kind IN ('notes', 'whiteboard'));

CREATE TABLE IF NOT EXISTS journal_drawings (
    drawing_id   SERIAL PRIMARY KEY,
    page_id      INT NOT NULL REFERENCES journal_pages (page_id) ON DELETE CASCADE,
    board        BOOLEAN NOT NULL DEFAULT false,     -- the whole page of a whiteboard page
    scene        JSONB NOT NULL DEFAULT '{}'::jsonb, -- {elements: [...], appState: {background, grid}}
    files        JSONB NOT NULL DEFAULT '{}'::jsonb, -- pictures on the canvas: {id: {mimeType, dataURL}}
    text         TEXT NOT NULL DEFAULT '',           -- words written on it with the text tool
    preview      BYTEA,                              -- PNG of the whole drawing
    preview_type TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS journal_drawings_page_idx ON journal_drawings (page_id);
CREATE UNIQUE INDEX IF NOT EXISTS journal_drawings_one_board_uq ON journal_drawings (page_id) WHERE board;

DROP TRIGGER IF EXISTS journal_drawings_set_updated_at ON journal_drawings;
CREATE TRIGGER journal_drawings_set_updated_at
    BEFORE UPDATE ON journal_drawings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
