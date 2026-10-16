-- Board games you play but don't own (a friend's copy, a games café): status 'Played elsewhere'.
-- And plays that didn't finish (abandoned): board_game_plays.finished = false (no winner then).
-- Idempotent: the status CHECK is replaced only while it lacks the new status.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'board_games'::regclass
                   AND pg_get_constraintdef(oid) LIKE '%Played elsewhere%') THEN
        ALTER TABLE board_games DROP CONSTRAINT IF EXISTS board_games_status_check;
        ALTER TABLE board_games ADD CONSTRAINT board_games_status_check
            CHECK (status IN ('Owned', 'To sell', 'Wanted', 'Borrowed', 'Played elsewhere', 'Gone'));
    END IF;
END $$;

ALTER TABLE board_game_plays ADD COLUMN IF NOT EXISTS finished BOOLEAN NOT NULL DEFAULT true;
