-- Board games, the second hobby module (2026-10-13).
--
--   board_games       your collection: status Owned / Wanted / Borrowed (a copy you play but
--                     don't own) / Gone, players, play time, what you paid, your rating, a photo
--   board_game_plays  each time you played: the day, who played, who won, how long, notes
--
-- Plays show on the calendar and in Recent activity; "Played @Catan tonight" in the journal
-- offers to log a play (api/app/journal_actions.py).
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS board_games (
    game_id       SERIAL PRIMARY KEY,
    name          TEXT NOT NULL CHECK (btrim(name) <> ''),
    publisher     TEXT,
    year          INT CHECK (year BETWEEN 1800 AND 2200),
    min_players   INT CHECK (min_players >= 1),
    max_players   INT,
    play_minutes  INT CHECK (play_minutes > 0),
    status        TEXT NOT NULL DEFAULT 'Owned' CHECK (status IN ('Owned', 'Wanted', 'Borrowed', 'Gone')),
    purchase_date DATE,
    price_paid    NUMERIC(10, 2) CHECK (price_paid >= 0),
    rating        INT CHECK (rating BETWEEN 1 AND 10),
    notes         TEXT,
    bgg_url       TEXT,                    -- the game's BoardGameGeek page, opened in your browser
    photo         BYTEA,
    photo_type    TEXT,
    photo_updated TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT board_games_players_check CHECK (max_players IS NULL OR min_players IS NULL OR max_players >= min_players)
);

DROP TRIGGER IF EXISTS board_games_set_updated_at ON board_games;
CREATE TRIGGER board_games_set_updated_at
    BEFORE UPDATE ON board_games
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS board_game_plays (
    play_id    SERIAL PRIMARY KEY,
    game_id    INT NOT NULL REFERENCES board_games (game_id) ON DELETE CASCADE,
    played_on  DATE NOT NULL DEFAULT current_date,
    players    TEXT,                       -- "Sam, Alex, Jo"
    winner     TEXT,
    minutes    INT CHECK (minutes > 0),
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS board_game_plays_game_idx ON board_game_plays (game_id, played_on DESC);

-- Journal pages can @mention a game.
ALTER TABLE journal_links DROP CONSTRAINT IF EXISTS journal_links_target_kind_check;
ALTER TABLE journal_links ADD CONSTRAINT journal_links_target_kind_check
    CHECK (target_kind IN ('model', 'supply', 'page', 'game'));

COMMIT;
