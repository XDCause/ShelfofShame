-- Board games (2026-10-16): a "To sell" status - still yours (it counts as owned), but you mean to sell it.
BEGIN;

DO $$
DECLARE c TEXT;
BEGIN
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'board_games'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%status%'
    LOOP
        EXECUTE format('ALTER TABLE board_games DROP CONSTRAINT %I', c);
    END LOOP;
END $$;
ALTER TABLE board_games ADD CONSTRAINT board_games_status_check
    CHECK (status IN ('Owned', 'To sell', 'Wanted', 'Borrowed', 'Gone'));

COMMIT;
