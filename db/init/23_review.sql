-- From the review of 2026-10-14.
--
-- 1. model_log.photo_updated: when a build-log photo last changed. Photos are now cached by the
--    browser for a year, so their address must change with them (?v=<photo_updated>); the entry's
--    created_at doesn't change when its photo is replaced.
--
-- 2. Indexes on the foreign keys that didn't have one.
-- Postgres doesn't index a foreign key by itself. Without an index, joining on it or deleting the
-- row it points at (a brand, a mix, a calendar event...) reads the whole referring table. The
-- tables are small today, so this is for later; each index costs next to nothing.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE model_log ADD COLUMN IF NOT EXISTS photo_updated TIMESTAMPTZ;
UPDATE model_log SET photo_updated = created_at WHERE photo IS NOT NULL AND photo_updated IS NULL;

CREATE INDEX IF NOT EXISTS colour_group_members_group_idx ON colour_group_members (group_id);
CREATE INDEX IF NOT EXISTS journal_images_page_idx ON journal_images (page_id);
CREATE INDEX IF NOT EXISTS mix_parts_brand_idx ON mix_parts (brand_id);
CREATE INDEX IF NOT EXISTS model_paints_brand_idx ON model_paints (brand_id);
CREATE INDEX IF NOT EXISTS model_paints_mix_idx ON model_paints (mix_id);
CREATE INDEX IF NOT EXISTS models_brand_idx ON models (brand_id);
CREATE INDEX IF NOT EXISTS page_tags_tag_idx ON page_tags (tag_id);
CREATE INDEX IF NOT EXISTS volleyball_games_event_idx ON volleyball_games (event_id);
CREATE INDEX IF NOT EXISTS volleyball_videos_game_idx ON volleyball_videos (game_id);
CREATE INDEX IF NOT EXISTS wishlist_category_idx ON wishlist (category_id);
