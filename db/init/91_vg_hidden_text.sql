-- Hidden achievements' text (2026-10-27). Steam leaves a hidden achievement's description empty; SteamHunters' API has
-- it. Read once per game, the first time its panel is opened (videogames.py, GET /api/videogames/hidden/{app_id}), and
-- kept: the panel shows it only when you press the eye (or Show hidden).
--
--   vg_hidden_text   each hidden achievement's text, by Steam app id and api name - so a Ubisoft game's list (its Steam
--                    version's, othergames.py) shares the Steam game's. No foreign key on purpose: the same app id can
--                    be a Steam game, a Ubisoft game's Steam version or both.
--   vg_hidden_read   which games have been asked (also when SteamHunters had nothing): asked once, never again
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE TABLE IF NOT EXISTS vg_hidden_text (
    app_id      INT  NOT NULL,                -- Steam's id for the game
    api_name    TEXT NOT NULL,                -- Steam's id for the achievement
    description TEXT NOT NULL,
    PRIMARY KEY (app_id, api_name)
);

CREATE TABLE IF NOT EXISTS vg_hidden_read (
    app_id  INT PRIMARY KEY,
    read_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
