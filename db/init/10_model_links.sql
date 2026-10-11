-- A Scalemates link per model (2026-10-12). Pasted by the user and opened in their own
-- browser - the app never fetches it (Scalemates disallows scraping; see CLAUDE.md 3i).
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\10_model_links.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

ALTER TABLE models ADD COLUMN IF NOT EXISTS scalemates_url TEXT;

COMMIT;
