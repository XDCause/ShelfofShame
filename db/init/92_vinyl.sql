-- Vinyl (2026-11-11), a hobby module: your records, every time you played one, and what they're worth.
--
--   vinyl_records   your collection and wantlist: Owned / Wanted / Gone, the pressing (Discogs' release: label, catalogue
--                   number, country, year, format, variant, tracklist, genres and styles), your copy (the record's and
--                   the sleeve's grade, what you paid, where, the shelf it's on, notes, stars), the cover (downloaded
--                   once and kept here, so it works in the offline copy) and today's value
--   vinyl_values    each record's value as it was checked (weekly), for the value-over-time chart
--   vinyl_plays     the listening log: when, which sides, a note; and whether it went to Last.fm
--   vinyl_settings  one row: the Discogs account the collection syncs with, Last.fm's session
--
-- Grades are the Goldmine scale Discogs uses: M, NM, VG+, VG, G+, G, F, P (a sleeve can also be Generic or No cover).
-- Plays show on the calendar and in Recent activity; records can be @mentioned in the journal and sit on the wishlist.
-- Must match api/app/vinyl.py (STATUSES, MEDIUMS, FORMATS, GRADES) and db.MODULE_IDS.
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS vinyl_records (
    record_id           SERIAL PRIMARY KEY,
    title               TEXT NOT NULL CHECK (btrim(title) <> ''),
    artist              TEXT,
    status              TEXT NOT NULL DEFAULT 'Owned' CHECK (status IN ('Owned', 'Wanted', 'Gone')),
    medium              TEXT NOT NULL DEFAULT 'Vinyl' CHECK (medium IN ('Vinyl', 'CD', 'Cassette', 'Other')),
    format              TEXT NOT NULL DEFAULT 'LP' CHECK (format IN ('LP', 'EP', 'Single', 'Box set', 'Other')),
    size                TEXT CHECK (size IN ('12"', '10"', '7"')),
    discs               INT NOT NULL DEFAULT 1 CHECK (discs BETWEEN 1 AND 100),
    year                INT CHECK (year BETWEEN 1880 AND 2200),          -- this pressing
    original_year       INT CHECK (original_year BETWEEN 1880 AND 2200), -- the album's first release (Discogs' master)
    country             TEXT,
    label               TEXT,
    catno               TEXT,                                            -- the label's catalogue number
    barcode             TEXT,
    variant             TEXT,                                            -- "Red translucent, 180 gram, Limited Edition"
    genres              TEXT[] NOT NULL DEFAULT '{}',
    styles              TEXT[] NOT NULL DEFAULT '{}',
    tracklist           JSONB NOT NULL DEFAULT '[]',                     -- [{position: "A1", title, duration: "3:41"}]
    discogs_release_id  BIGINT,
    discogs_master_id   BIGINT,
    discogs_instance_id BIGINT,                                          -- this copy in your Discogs collection
    media_condition     TEXT CHECK (media_condition IN ('M', 'NM', 'VG+', 'VG', 'G+', 'G', 'F', 'P')),
    sleeve_condition    TEXT CHECK (sleeve_condition IN ('M', 'NM', 'VG+', 'VG', 'G+', 'G', 'F', 'P', 'Generic', 'No cover')),
    price_paid          NUMERIC(10, 2) CHECK (price_paid >= 0),
    purchase_date       DATE,
    bought_from         TEXT,
    added_on            DATE NOT NULL DEFAULT current_date,              -- in your collection since (Discogs' date added)
    rating              INT CHECK (rating BETWEEN 1 AND 5),
    notes               TEXT,
    location_id         INT REFERENCES storage_locations (location_id) ON DELETE SET NULL,   -- the shelf / crate
    have_count          INT,                                             -- Discogs: people who have it / want it
    want_count          INT,
    community_rating    NUMERIC(3, 2),
    lowest_price        NUMERIC(10, 2),                                  -- the cheapest copy for sale on Discogs (AUD)
    for_sale            INT,
    value               NUMERIC(10, 2) CHECK (value >= 0),               -- what yours is worth today (AUD)
    value_note          TEXT,                                            -- where that came from
    value_checked_at    TIMESTAMPTZ,
    details_at          TIMESTAMPTZ,                                     -- when Discogs' full release was last read
    cover_url           TEXT,                                            -- Discogs' cover image, fetched once into photo
    photo               BYTEA,
    photo_type          TEXT,
    photo_updated       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS vinyl_records_instance_uq ON vinyl_records (discogs_instance_id) WHERE discogs_instance_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS vinyl_records_release_idx ON vinyl_records (discogs_release_id);

DROP TRIGGER IF EXISTS vinyl_records_set_updated_at ON vinyl_records;
CREATE TRIGGER vinyl_records_set_updated_at
    BEFORE UPDATE ON vinyl_records
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS vinyl_values (
    value_id  SERIAL PRIMARY KEY,
    record_id INT NOT NULL REFERENCES vinyl_records (record_id) ON DELETE CASCADE,
    value     NUMERIC(10, 2) NOT NULL CHECK (value >= 0),
    note      TEXT,
    seen_on   DATE NOT NULL DEFAULT current_date,
    CONSTRAINT vinyl_values_day_uq UNIQUE (record_id, seen_on)                  -- one a day: a later check replaces it
);

CREATE TABLE IF NOT EXISTS vinyl_plays (
    play_id        SERIAL PRIMARY KEY,
    record_id      INT NOT NULL REFERENCES vinyl_records (record_id) ON DELETE CASCADE,
    played_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    sides          TEXT,                                                 -- "A, B"; empty = the whole record
    note           TEXT,
    scrobbled      INT,                                                  -- tracks sent to Last.fm
    scrobble_error TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS vinyl_plays_record_idx ON vinyl_plays (record_id, played_at DESC);
CREATE INDEX IF NOT EXISTS vinyl_plays_when_idx ON vinyl_plays (played_at DESC);

CREATE TABLE IF NOT EXISTS vinyl_settings (
    id                INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    discogs_username  TEXT,
    discogs_synced_at TIMESTAMPTZ,
    discogs_error     TEXT,
    discogs_mirror    BOOLEAN NOT NULL DEFAULT false,   -- records added here go into your Discogs collection too
    lastfm_user       TEXT,
    lastfm_session    TEXT,                             -- Last.fm's session key (never sent to the browser)
    lastfm_token      TEXT,                             -- while you're allowing the app on last.fm
    lastfm_auto       BOOLEAN NOT NULL DEFAULT true     -- a play is scrobbled unless you untick it
);
INSERT INTO vinyl_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Calendar events for the Vinyl hobby too (keep in step with db.MODULE_IDS).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'calendar_events'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%vinyl%') THEN
        ALTER TABLE calendar_events DROP CONSTRAINT IF EXISTS calendar_events_hobby_check;
        ALTER TABLE calendar_events ADD CONSTRAINT calendar_events_hobby_check
            CHECK (hobby IN ('models', 'boardgames', 'volleyball', 'videogames', 'chess', 'reading', 'car', 'travel', 'shooting',
                             'hiking', 'gardening', 'vinyl'));
    END IF;
END $$;

-- Journal pages can @mention a record. ('trip' too: the editor offered trips since 77_travel, but this list never had
-- them, so saving a page that mentioned a trip failed.)
ALTER TABLE journal_links DROP CONSTRAINT IF EXISTS journal_links_target_kind_check;
ALTER TABLE journal_links ADD CONSTRAINT journal_links_target_kind_check
    CHECK (target_kind IN ('model', 'supply', 'page', 'game', 'gear', 'videogame', 'chess', 'book', 'trip', 'record'));

-- Wanted records are on the wishlist (kind 'record'), with its extras and price history.
ALTER TABLE wanted_extras DROP CONSTRAINT IF EXISTS wanted_extras_kind_check;
ALTER TABLE wanted_extras ADD CONSTRAINT wanted_extras_kind_check CHECK (kind IN ('wish', 'model', 'game', 'gear', 'garden', 'record'));
ALTER TABLE wanted_prices DROP CONSTRAINT IF EXISTS wanted_prices_kind_check;
ALTER TABLE wanted_prices ADD CONSTRAINT wanted_prices_kind_check CHECK (kind IN ('wish', 'model', 'game', 'gear', 'garden', 'record'));
DROP TRIGGER IF EXISTS vinyl_records_drop_wanted ON vinyl_records;
CREATE TRIGGER vinyl_records_drop_wanted AFTER DELETE ON vinyl_records FOR EACH ROW EXECUTE FUNCTION drop_wanted_extras('record', 'record_id');

COMMIT;
