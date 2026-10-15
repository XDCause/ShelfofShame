-- Half stars for books (2026-10-15): a rating is 0.5 to 5 in steps of a half (3.5 = ★★★½).
-- Was SMALLINT 1-5; whole ratings already stored keep their value.
BEGIN;

DO $$
DECLARE c TEXT;
BEGIN
    -- the old CHECK (rating BETWEEN 1 AND 5) has a generated name; find it rather than guess
    FOR c IN SELECT conname FROM pg_constraint
             WHERE conrelid = 'books'::regclass AND contype = 'c' AND pg_get_constraintdef(oid) LIKE '%rating%'
    LOOP
        EXECUTE format('ALTER TABLE books DROP CONSTRAINT %I', c);
    END LOOP;
END $$;

ALTER TABLE books ALTER COLUMN rating TYPE NUMERIC(2,1);
ALTER TABLE books ADD CONSTRAINT books_rating_halves
    CHECK (rating BETWEEN 0.5 AND 5 AND rating * 2 = trunc(rating * 2));

COMMIT;
