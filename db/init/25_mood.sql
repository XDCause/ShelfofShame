-- Mood in the journal (2026-10-14), replacing the page icon.
--
--   journal_pages.mood        how the day felt: great / good / okay / meh / rough (or not set)
--   journal_pages.mood_words  a word or two about it: tired, proud, relaxed...
--   journal_pages.icon        dropped: the emoji beside the title is now the mood (no page used
--                             an icon when this was written)
--
-- The faces and words shown for each mood are in web/src/core/journal/moods.js; the ids here
-- must match MOODS in api/app/db.py.
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS mood TEXT;
ALTER TABLE journal_pages ADD COLUMN IF NOT EXISTS mood_words TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE journal_pages DROP CONSTRAINT IF EXISTS journal_pages_mood_check;
ALTER TABLE journal_pages ADD CONSTRAINT journal_pages_mood_check
    CHECK (mood IS NULL OR mood IN ('great', 'good', 'okay', 'meh', 'rough'));
ALTER TABLE journal_pages DROP COLUMN IF EXISTS icon;

CREATE INDEX IF NOT EXISTS journal_pages_mood_day_idx ON journal_pages (entry_date) WHERE mood IS NOT NULL;

COMMIT;
