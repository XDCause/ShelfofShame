-- Raw or edited: a long video straight off the phone (raw, to cut clips from) or a finished one
-- (edited: a highlight video the app made, or one you edited elsewhere). NULL = a link (YouTube...).
-- Idempotent: the backfill only fills rows that have no value yet.
ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS edit TEXT CHECK (edit IN ('raw', 'edited'));
UPDATE volleyball_videos SET edit = CASE WHEN made_from IS NOT NULL THEN 'edited' ELSE 'raw' END
WHERE edit IS NULL AND (file_name IS NOT NULL OR made_from IS NOT NULL);
