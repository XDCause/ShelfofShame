-- The journal grows (2026-10-21, user: "do them all" from a scan of Day One, Apple Journal, Notion, reMarkable...):
--   notebooks       separate journals (Personal, Build logs, Travel), each with a colour; a page is in one or none
--   templates       pages you saved to start new ones from (the built-in ones live in the web app)
--   a page's place  where it was written (name + lat / lon: the journal's map) and that day's weather there
--   paper           plain, lined, grid or dot behind a notes page
--   private         kept out of Home, the activity feed, search, On this day and the list (unless you ask)
-- Idempotent.

CREATE TABLE IF NOT EXISTS journal_notebooks (
    notebook_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE CHECK (length(trim(name)) BETWEEN 1 AND 40),
    colour      TEXT NOT NULL DEFAULT 'teal',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS journal_templates (
    template_id SERIAL PRIMARY KEY,
    name        TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 60),
    title       TEXT NOT NULL DEFAULT '',
    content     JSONB NOT NULL DEFAULT '[]',
    tags        TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS notebook_id INT REFERENCES journal_notebooks (notebook_id) ON DELETE SET NULL;
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS place_name TEXT;
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS lat NUMERIC(8, 5);
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS lon NUMERIC(8, 5);
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS weather JSONB;          -- {sky, icon, max, min, rain_mm}
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS paper TEXT NOT NULL DEFAULT 'plain';
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS private BOOLEAN NOT NULL DEFAULT false;

DO $$ BEGIN
    ALTER TABLE journal_pages ADD CONSTRAINT journal_pages_paper_check CHECK (paper IN ('plain', 'lined', 'grid', 'dot'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE journal_pages ADD CONSTRAINT journal_pages_place_check
        CHECK ((lat IS NULL) = (lon IS NULL) AND (lat IS NULL OR (lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180)));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS journal_pages_notebook ON journal_pages (notebook_id);
