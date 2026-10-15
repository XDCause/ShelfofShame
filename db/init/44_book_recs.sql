-- Book recommendations (2026-10-15): picked from Open Library by reading_recs.py - more books by
-- authors you rated highly, and well-rated books in the genres you read - and kept here between
-- refreshes (weekly, or when your top authors / genres change), so pages don't ask Open Library.
BEGIN;

CREATE TABLE IF NOT EXISTS book_recs (
    ol_work     TEXT PRIMARY KEY,                    -- Open Library work id, e.g. OL21745884W
    section     TEXT NOT NULL CHECK (section IN ('author', 'genre')),
    reason      TEXT NOT NULL,                       -- the author's name, or the genre
    seed        TEXT,                                -- your book that led to it ("you gave Red Rising 5★")
    seed_rating NUMERIC(2,1),
    rank        INT NOT NULL,                        -- order on the page
    title       TEXT NOT NULL,
    author      TEXT,
    year        INT,
    pages       INT,
    cover_id    INT,
    isbn        TEXT,
    genres      TEXT[] NOT NULL DEFAULT '{}',
    ol_rating   NUMERIC(3,2),                        -- Open Library readers' average, and how many rated it
    ol_ratings  INT NOT NULL DEFAULT 0,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "Not interested": never suggested again (until you bring them back).
CREATE TABLE IF NOT EXISTS book_rec_dismissed (
    ol_work      TEXT PRIMARY KEY,
    title        TEXT,
    dismissed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
