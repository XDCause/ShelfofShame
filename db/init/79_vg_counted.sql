-- Video games (2026-10-20): achievements you tick off by hand - a Ubisoft game, or an Epic game added by hand using its
-- Steam version's list (Stranded Deep) - are shown with an asterisk; each such game can be left out of your completion,
-- goal and achievement totals (counted = false), while its own progress and its playtime still show. Idempotent.
ALTER TABLE vg_other_games ADD COLUMN IF NOT EXISTS counted boolean NOT NULL DEFAULT true;
