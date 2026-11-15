-- Board games at the table (2026-11-15): log a play as you sit down, not afterwards (user: "the tab is very
-- retroactive"). The people you play with, groups of them, scores, and plays still being played.
--
--   board_game_players       everyone you play with, once (one of them can be you: is_me)
--   board_game_groups        a usual group ("Thursday crew"): its players, added in one tap
--   board_game_play_players  who sat at a play: their score (and its parts / the +/- taps that made it), place,
--                            whether they won, team, colour or faction, and whether it was their first play of it
--   board_game_live          plays still being played: the timer's stages (setup / teach / play, paused or not),
--                            who's playing and the scores so far. Finishing one turns it into a board_game_plays row
--                            (so the calendar, goals and activity never count a half-played game) and deletes it.
--
-- New on board_game_plays: setup / teach minutes (minutes stays the playing time), when it started and ended, where,
-- the expansions used, who went first, and for a co-op game whether the table won. players / winner stay as
-- text ("Sam, Jo, Me") written by the API from the seats, so everything that reads them is unchanged.
-- New on board_games: how it's scored (highest / lowest wins, co-op, no score), its score sheet (the parts a score
-- is made of, e.g. Wingspan's birds, bonus cards, eggs...) and your notes for teaching it.
--
-- Plays logged before this had "Sam, Jo and me" as text: each name becomes a player (once) and a seat.
-- Must match api/app/boardgames_people.py and boardgames_live.py.
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

ALTER TABLE board_games ADD COLUMN IF NOT EXISTS scoring TEXT NOT NULL DEFAULT 'highest';
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS score_parts TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE board_games ADD COLUMN IF NOT EXISTS teach_notes TEXT;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'board_games_scoring_check') THEN
        ALTER TABLE board_games ADD CONSTRAINT board_games_scoring_check
            CHECK (scoring IN ('highest', 'lowest', 'coop', 'none'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS board_game_players (
    player_id  SERIAL PRIMARY KEY,
    name       TEXT NOT NULL CHECK (btrim(name) <> ''),
    is_me      BOOLEAN NOT NULL DEFAULT false,
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS board_game_players_name_idx ON board_game_players (lower(name));
CREATE UNIQUE INDEX IF NOT EXISTS board_game_players_me_idx ON board_game_players (is_me) WHERE is_me;

CREATE TABLE IF NOT EXISTS board_game_groups (
    group_id   SERIAL PRIMARY KEY,
    name       TEXT NOT NULL CHECK (btrim(name) <> ''),
    player_ids INT[] NOT NULL DEFAULT '{}',          -- a player deleted later is simply skipped
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS setup_minutes INT;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS teach_minutes INT;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS location TEXT;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS expansions INT[] NOT NULL DEFAULT '{}';     -- board_games ids
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS first_player_id INT REFERENCES board_game_players (player_id) ON DELETE SET NULL;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS coop_won BOOLEAN;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'board_game_plays_extra_minutes_check') THEN
        ALTER TABLE board_game_plays ADD CONSTRAINT board_game_plays_extra_minutes_check
            CHECK (setup_minutes >= 0 AND teach_minutes >= 0);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS board_game_play_players (
    play_id    INT NOT NULL REFERENCES board_game_plays (play_id) ON DELETE CASCADE,
    player_id  INT NOT NULL REFERENCES board_game_players (player_id),    -- a player in plays can't be deleted (merge them)
    seat       INT NOT NULL DEFAULT 0,                 -- the order they're listed in
    score      NUMERIC(10, 2),
    parts      JSONB,                                  -- {"Birds": 34, "Eggs": 12}: the game's score sheet
    adds       NUMERIC(10, 2)[] NOT NULL DEFAULT '{}', -- the +/- taps during the play, in order
    place      INT CHECK (place >= 1),
    won        BOOLEAN NOT NULL DEFAULT false,
    team       TEXT,
    colour     TEXT,                                   -- their colour or faction
    first_time BOOLEAN NOT NULL DEFAULT false,         -- their first play of this game
    PRIMARY KEY (play_id, player_id)
);
CREATE INDEX IF NOT EXISTS board_game_play_players_player_idx ON board_game_play_players (player_id);

CREATE TABLE IF NOT EXISTS board_game_live (
    live_id    SERIAL PRIMARY KEY,
    game_id    INT NOT NULL REFERENCES board_games (game_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    stages     JSONB NOT NULL DEFAULT '[]',            -- [{"stage": "setup", "from": "...", "to": "..."}]; the open one has no "to"
    paused     BOOLEAN NOT NULL DEFAULT false,
    seats      JSONB NOT NULL DEFAULT '[]',            -- [{"player_id", "score", "parts", "adds", "team", "colour", "won"}]
    location   TEXT,
    expansions INT[] NOT NULL DEFAULT '{}',
    first_player_id INT,
    notes      TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE board_game_live ADD COLUMN IF NOT EXISTS rounds INT NOT NULL DEFAULT 0;
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS rounds INT;                 -- the round counter, if you used it
ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS fun INT;                    -- how good a play it was, 1-5
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'board_game_plays_fun_check') THEN
        ALTER TABLE board_game_plays ADD CONSTRAINT board_game_plays_fun_check CHECK (fun BETWEEN 1 AND 5 AND rounds >= 0);
    END IF;
END $$;

-- Photos of a play (the final board, the table): taken during the play (live_id) or after (play_id). Finishing a
-- play moves its photos from the live play to the play.
CREATE TABLE IF NOT EXISTS board_game_play_photos (
    photo_id   SERIAL PRIMARY KEY,
    play_id    INT REFERENCES board_game_plays (play_id) ON DELETE CASCADE,
    live_id    INT REFERENCES board_game_live (live_id) ON DELETE CASCADE,
    photo      BYTEA NOT NULL,
    photo_type TEXT NOT NULL,
    caption    TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT board_game_play_photos_owner_check CHECK ((play_id IS NULL) <> (live_id IS NULL))
);
CREATE INDEX IF NOT EXISTS board_game_play_photos_play_idx ON board_game_play_photos (play_id);

-- Plays from before: "Alex Morgan, Robin and Kit" -> a player each (once, any case) and a seat each, in order. The
-- winner is the listed player with that name, or whose name starts with it (winner "Alex" is Alex Morgan, not a
-- fourth player); a winner who isn't listed at all played too. "Everyone" (or all of us, we) won together; a team
-- ("Team blue") isn't a person.
DROP TABLE IF EXISTS bg_old_seats;
CREATE TEMP TABLE bg_old_seats ON COMMIT DROP AS
WITH todo AS (
    SELECT play_id, players, winner FROM board_game_plays p
    WHERE NOT EXISTS (SELECT 1 FROM board_game_play_players s WHERE s.play_id = p.play_id)),
listed AS (
    SELECT t.play_id, btrim(x.n) AS name, x.i FROM todo t,
           regexp_split_to_table(coalesce(t.players, ''), '\s*(,|&|\s+and\s+)\s*') WITH ORDINALITY x(n, i)
    WHERE btrim(x.n) <> ''),
won AS (
    SELECT t.play_id, btrim(w) AS name FROM todo t, regexp_split_to_table(coalesce(t.winner, ''), '\s*(,|&|\s+and\s+)\s*') w
    WHERE btrim(w) <> '' AND lower(btrim(w)) NOT IN ('everyone', 'all', 'all of us', 'we', 'us') AND lower(btrim(w)) NOT LIKE 'team %'),
together AS (
    SELECT play_id FROM todo WHERE lower(btrim(winner)) IN ('everyone', 'all', 'all of us', 'we', 'us')),
won_as AS (
    SELECT w.play_id, coalesce((SELECT l.name FROM listed l WHERE l.play_id = w.play_id
                                  AND (lower(l.name) = lower(w.name) OR lower(l.name) LIKE lower(w.name) || ' %')
                                ORDER BY lower(l.name) = lower(w.name) DESC, l.i LIMIT 1), w.name) AS name
    FROM won w)
SELECT play_id, min(name) AS name, min(i) AS i, bool_or(won) OR play_id IN (SELECT play_id FROM together) AS won FROM (
    SELECT play_id, name, i, false AS won FROM listed
    UNION ALL SELECT play_id, name, 1000, true FROM won_as) x
GROUP BY play_id, lower(name);

INSERT INTO board_game_players (name)
SELECT DISTINCT ON (lower(name)) name FROM bg_old_seats s
WHERE NOT EXISTS (SELECT 1 FROM board_game_players x WHERE lower(x.name) = lower(s.name));

UPDATE board_game_players SET is_me = true
WHERE player_id = (SELECT min(player_id) FROM board_game_players WHERE lower(name) IN ('me', 'myself'))
  AND NOT EXISTS (SELECT 1 FROM board_game_players WHERE is_me);

INSERT INTO board_game_play_players (play_id, player_id, seat, won)
SELECT s.play_id, pl.player_id, row_number() OVER (PARTITION BY s.play_id ORDER BY s.i, s.name)::int, s.won
FROM bg_old_seats s JOIN board_game_players pl ON lower(pl.name) = lower(s.name);

-- Their first play of each game: the earliest seat per player and game.
UPDATE board_game_play_players s SET first_time = true
FROM (SELECT DISTINCT ON (s2.player_id, p.game_id) s2.play_id, s2.player_id, p.game_id
      FROM board_game_play_players s2 JOIN board_game_plays p USING (play_id)
      ORDER BY s2.player_id, p.game_id, p.played_on, p.play_id) f
WHERE s.play_id = f.play_id AND s.player_id = f.player_id
  AND NOT EXISTS (SELECT 1 FROM board_game_play_players t JOIN board_game_plays tp USING (play_id)
                  WHERE t.first_time AND t.player_id = f.player_id AND tp.game_id = f.game_id);

COMMIT;
