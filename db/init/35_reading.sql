-- Reading: a hobby module for books (2026-10-14).
--
--   books        every book: what it is (title, author, cover, pages - from Open Library or typed),
--                where you are with it (want / reading / finished / dnf, the page you're on, dates),
--                and what you thought (1-5 stars, a review). goodreads_id = imported from Goodreads.
--   reading_log  each time you update your page: the page reached and the pages read since the
--                last update, on a day (pages per day / month, the calendar and the activity feed)
--   book_quotes  quotes you saved, with the page
-- The yearly goal lives in settings (reading_goal_<year> = books).
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

CREATE TABLE IF NOT EXISTS books (
    book_id       SERIAL PRIMARY KEY,
    title         TEXT NOT NULL CHECK (title <> ''),
    author        TEXT,
    isbn          TEXT,                     -- ISBN-13 when known (digits only)
    ol_work       TEXT,                     -- Open Library's work key, "OL27448W"
    cover_id      INT,                      -- Open Library cover id -> covers.openlibrary.org/b/id/<id>-M.jpg
    pages         INT CHECK (pages > 0),
    year          INT,                      -- first published
    genres        TEXT[] NOT NULL DEFAULT '{}',
    format        TEXT CHECK (format IN ('paper', 'ebook', 'audio')),
    status        TEXT NOT NULL DEFAULT 'want' CHECK (status IN ('want', 'reading', 'finished', 'dnf')),
    current_page  INT CHECK (current_page >= 0),
    started_on    DATE,
    finished_on   DATE,                     -- finished, or gave up (dnf)
    rating        SMALLINT CHECK (rating BETWEEN 1 AND 5),
    review        TEXT,
    goodreads_id  TEXT,
    looked_up_at  TIMESTAMPTZ,              -- Open Library asked for its cover / details (NULL = not yet)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS books_goodreads_uq ON books (goodreads_id) WHERE goodreads_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS books_status_idx ON books (status);
CREATE INDEX IF NOT EXISTS books_finished_idx ON books (finished_on);

DROP TRIGGER IF EXISTS books_updated_at ON books;
CREATE TRIGGER books_updated_at BEFORE UPDATE ON books FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS reading_log (
    log_id      SERIAL PRIMARY KEY,
    book_id     INT NOT NULL REFERENCES books (book_id) ON DELETE CASCADE,
    logged_on   DATE NOT NULL DEFAULT current_date,
    page        INT NOT NULL CHECK (page >= 0),      -- the page you got to
    pages       INT NOT NULL DEFAULT 0 CHECK (pages >= 0),   -- pages read since the update before
    minutes     INT CHECK (minutes > 0),
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS reading_log_book_idx ON reading_log (book_id, logged_on);
CREATE INDEX IF NOT EXISTS reading_log_day_idx ON reading_log (logged_on);

CREATE TABLE IF NOT EXISTS book_quotes (
    quote_id    SERIAL PRIMARY KEY,
    book_id     INT NOT NULL REFERENCES books (book_id) ON DELETE CASCADE,
    text        TEXT NOT NULL CHECK (text <> ''),
    page        INT CHECK (page >= 0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS book_quotes_book_idx ON book_quotes (book_id);

ALTER TABLE journal_links DROP CONSTRAINT IF EXISTS journal_links_target_kind_check;
ALTER TABLE journal_links ADD CONSTRAINT journal_links_target_kind_check
    CHECK (target_kind IN ('model', 'supply', 'page', 'game', 'gear', 'videogame', 'chess', 'book'));
