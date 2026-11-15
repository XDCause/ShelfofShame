-- Indexes on foreign-key columns that had none (2026-11-16, a database health check: 23 of them). PostgreSQL indexes
-- the referenced side (a primary key) but not the referring column, so deleting a rifle / a garden space / a model
-- had to read every row of the tables that point at it, and joins on those columns did the same. The tables are small
-- today; this keeps them quick as they grow. Partial (WHERE col IS NOT NULL) where most rows leave it empty.
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

BEGIN;

CREATE INDEX IF NOT EXISTS vinyl_records_location_idx ON vinyl_records (location_id) WHERE location_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS shooting_sessions_rifle_idx ON shooting_sessions (rifle_id);
CREATE INDEX IF NOT EXISTS shooting_sessions_ammo_idx ON shooting_sessions (ammo_id);
CREATE INDEX IF NOT EXISTS shooting_sessions_range_idx ON shooting_sessions (range_id);
CREATE INDEX IF NOT EXISTS shooting_media_group_idx ON shooting_media (group_id) WHERE group_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS dope_rows_rifle_idx ON dope_rows (rifle_id);
CREATE INDEX IF NOT EXISTS dope_rows_ammo_idx ON dope_rows (ammo_id);
CREATE INDEX IF NOT EXISTS garden_items_guide_idx ON garden_items (guide_id) WHERE guide_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_plantings_guide_idx ON garden_plantings (guide_id) WHERE guide_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_plantings_parent_idx ON garden_plantings (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_plantings_item_idx ON garden_plantings (item_id) WHERE item_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_logs_space_idx ON garden_logs (space_id) WHERE space_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_tasks_planting_idx ON garden_tasks (planting_id) WHERE planting_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_tasks_container_idx ON garden_tasks (container_id) WHERE container_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS garden_tasks_space_idx ON garden_tasks (space_id) WHERE space_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS trip_plan_place_idx ON trip_plan (place_id) WHERE place_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS trip_packing_gear_idx ON trip_packing (gear_id) WHERE gear_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS storage_locations_parent_idx ON storage_locations (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS supplies_reserved_model_idx ON supplies (reserved_model_id) WHERE reserved_model_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS todos_supply_idx ON todos (supply_id) WHERE supply_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS todos_gear_idx ON todos (gear_id) WHERE gear_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS wanted_extras_model_idx ON wanted_extras (for_model_id) WHERE for_model_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS wanted_extras_goal_idx ON wanted_extras (for_goal_id) WHERE for_goal_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS board_game_plays_first_idx ON board_game_plays (first_player_id) WHERE first_player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS board_game_live_game_idx ON board_game_live (game_id);
CREATE INDEX IF NOT EXISTS board_game_play_photos_live_idx ON board_game_play_photos (live_id) WHERE live_id IS NOT NULL;

COMMIT;
