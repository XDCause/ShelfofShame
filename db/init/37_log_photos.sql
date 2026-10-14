-- Build-log entries can have several photos (2026-10-14).
--
--   model_log_photos   each photo of a build-log entry, in the order added. A photo is never
--                      changed (only added or removed), so its address /api/model-log-photos/<id>
--                      can be cached for good.
--
-- The one photo an entry could have before (model_log.photo) moves here, then those columns go.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

CREATE TABLE IF NOT EXISTS model_log_photos (
    photo_id    SERIAL PRIMARY KEY,
    entry_id    INT NOT NULL REFERENCES model_log (entry_id) ON DELETE CASCADE,
    photo       BYTEA NOT NULL,
    photo_type  TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_log_photos_entry_idx ON model_log_photos (entry_id, photo_id);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'model_log' AND column_name = 'photo') THEN
        INSERT INTO model_log_photos (entry_id, photo, photo_type, created_at)
        SELECT entry_id, photo, COALESCE(photo_type, 'image/jpeg'), COALESCE(photo_updated, created_at)
        FROM model_log WHERE photo IS NOT NULL;
        ALTER TABLE model_log DROP COLUMN photo;
        ALTER TABLE model_log DROP COLUMN IF EXISTS photo_type;
        ALTER TABLE model_log DROP COLUMN IF EXISTS photo_updated;
    END IF;
END $$;
