-- The journal (2026-10-13): Notion-style pages, part of the core (not a hobby module).
--
--   journal_pages     one page: title, emoji, date, the editor's blocks (JSON) and their plain
--                     text (for search), pinned
--   tags, page_tags   your own labels on pages
--   journal_links     what each page @mentions (a model, a supply, another page), worked out
--                     from the blocks on every save, so a model can list the pages about it
--   journal_images    photos added to pages (served at /api/journal/images/<id>)
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS journal_pages (
    page_id    SERIAL PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '',
    icon       TEXT,                                  -- an emoji, optional
    entry_date DATE NOT NULL DEFAULT current_date,    -- the day it's about
    content    JSONB NOT NULL DEFAULT '[]'::jsonb,    -- BlockNote blocks
    text       TEXT NOT NULL DEFAULT '',              -- plain text of the blocks, for search
    pinned     BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS journal_pages_date_idx ON journal_pages (entry_date DESC, page_id DESC);

-- updated_at on every change (set_updated_at() comes from 01_schema.sql)
DROP TRIGGER IF EXISTS journal_pages_updated_at ON journal_pages;
CREATE TRIGGER journal_pages_updated_at BEFORE UPDATE ON journal_pages
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS tags (
    tag_id SERIAL PRIMARY KEY,
    name   TEXT NOT NULL,
    CONSTRAINT tags_name_uq UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS page_tags (
    page_id INT NOT NULL REFERENCES journal_pages (page_id) ON DELETE CASCADE,
    tag_id  INT NOT NULL REFERENCES tags (tag_id) ON DELETE CASCADE,
    PRIMARY KEY (page_id, tag_id)
);

CREATE TABLE IF NOT EXISTS journal_links (
    page_id     INT NOT NULL REFERENCES journal_pages (page_id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('model', 'supply', 'page')),
    target_id   INT NOT NULL,
    PRIMARY KEY (page_id, target_kind, target_id)
);
CREATE INDEX IF NOT EXISTS journal_links_target_idx ON journal_links (target_kind, target_id);

CREATE TABLE IF NOT EXISTS journal_images (
    image_id   SERIAL PRIMARY KEY,
    page_id    INT REFERENCES journal_pages (page_id) ON DELETE SET NULL,
    image      BYTEA NOT NULL,
    image_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
