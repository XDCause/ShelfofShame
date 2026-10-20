-- Video games (2026-10-20): playtime over time, and a photo for games you add by hand.
--   vg_playtime    each game's total playtime on a day (Steam, Epic, Ubisoft: platform + the app_id the app uses,
--                  "730" or "epic-12"). Taken at every sync and whenever you type hours in. What you played on a day
--                  = that day's total less the one before: Steam only gives totals, so the history starts here.
--   vg_other_games.photo   your own picture for an Epic / Ubisoft game added by hand (Fortnite has no Steam version).
-- Idempotent.
BEGIN;

CREATE TABLE IF NOT EXISTS vg_playtime (
    platform text NOT NULL CHECK (platform IN ('steam', 'epic', 'ubisoft')),
    app_id   text NOT NULL,
    day      date NOT NULL DEFAULT current_date,
    minutes  integer NOT NULL CHECK (minutes >= 0),
    PRIMARY KEY (platform, app_id, day)
);

ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS photo bytea;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS photo_type text;
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS photo_updated timestamptz;

-- Today's totals: the starting point (from tomorrow, each day's playing shows).
INSERT INTO vg_playtime (platform, app_id, minutes)
SELECT 'steam', app_id::text, playtime_minutes FROM vg_games WHERE playtime_minutes IS NOT NULL
ON CONFLICT DO NOTHING;
INSERT INTO vg_playtime (platform, app_id, minutes)
SELECT platform, platform || '-' || game_id, COALESCE(my_minutes, exo_minutes) FROM vg_other_games
WHERE COALESCE(my_minutes, exo_minutes) IS NOT NULL
ON CONFLICT DO NOTHING;

COMMIT;
