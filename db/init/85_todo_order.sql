-- Your own order for to-dos without a day (2026-10-21, user: "reorganise Next up by clicking and dragging"): a dated
-- to-do sorts by its day; undated ones by sort_order (set by dragging), then as before. NULL = never placed. Idempotent.

ALTER TABLE todos ADD COLUMN IF NOT EXISTS sort_order INT;
