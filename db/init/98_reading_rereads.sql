-- Reading: re-reads (2026-11-16).
--
--   book_reads  the EARLIER read-throughs of a book: when you started and finished it, how it ended, your stars and
--               review then. "Read it again" copies the book's current read here and starts the book afresh, so the
--               books row is always the read you're on (or the latest). Nothing existing changes: a book read once
--               has no rows here, and its books row is its one read.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

CREATE TABLE IF NOT EXISTS book_reads (
    read_id     SERIAL PRIMARY KEY,
    book_id     INT NOT NULL REFERENCES books (book_id) ON DELETE CASCADE,
    started_on  DATE,
    finished_on DATE,
    outcome     TEXT NOT NULL DEFAULT 'finished' CHECK (outcome IN ('finished', 'dnf')),
    rating      NUMERIC(2,1) CHECK (rating BETWEEN 0.5 AND 5 AND rating * 2 = round(rating * 2)),   -- halves, like books
    review      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS book_reads_book_idx ON book_reads (book_id, finished_on);
