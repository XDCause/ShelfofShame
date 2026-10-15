-- Books (2026-10-15):
--   * a new shelf, 'owned' = "On my shelf": books you have but haven't started (Want to read = ones
--     you'd like but don't have yet);
--   * series: the series a book is in and its number in it. Goodreads puts these in the title -
--     "Red Rising (Red Rising Saga, #1)" - so they're moved out of the titles into their own columns;
--   * book_series_cache: each series' full list (Wikidata + Open Library, bookseries.py), kept a week.
BEGIN;

DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'books'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%status%'
    LOOP
        EXECUTE format('ALTER TABLE books DROP CONSTRAINT %I', c);
    END LOOP;
END $$;
ALTER TABLE books ADD CONSTRAINT books_status_check CHECK (status IN ('want', 'owned', 'reading', 'finished', 'dnf'));

ALTER TABLE books ADD COLUMN IF NOT EXISTS series        TEXT;
ALTER TABLE books ADD COLUMN IF NOT EXISTS series_number NUMERIC(6,2) CHECK (series_number >= 0);

-- "Golden Son (Red Rising Saga, #2)" -> title "Golden Son", series "Red Rising Saga", number 2.
UPDATE books
SET series = m[1], series_number = m[2]::numeric, title = btrim(regexp_replace(title, '\s*\([^()]+,\s*#[0-9.]+\)\s*$', ''))
FROM (SELECT book_id AS id, regexp_match(title, '\(([^()]+),\s*#([0-9]+(?:\.[0-9]+)?)\)\s*$') AS m FROM books) x
WHERE books.book_id = x.id AND x.m IS NOT NULL AND books.series IS NULL;

CREATE INDEX IF NOT EXISTS books_series_idx ON books (lower(series));

CREATE TABLE IF NOT EXISTS book_series_cache (
    key        TEXT PRIMARY KEY,                -- lower-case "series|first author"
    source     TEXT,                            -- wikidata / openlibrary / NULL = found nothing
    books      JSONB NOT NULL DEFAULT '[]',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
