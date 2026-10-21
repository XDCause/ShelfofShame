-- (health check, 2026-10-21) The wishlist's extras and price history point at a wanted thing by (kind, ref)
-- (89_wishlist_more.sql): five tables, so no foreign key - and deleting a kit, game, piece of gear, garden thing or
-- supply wish left its extras and prices behind. A trigger on each of the five removes them. The bought history
-- (wanted_history) stays: it's a record of what happened, and names what it was.
-- Idempotent: safe to run again.
CREATE OR REPLACE FUNCTION drop_wanted_extras() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    gone INT := (to_jsonb(OLD) ->> TG_ARGV[1])::int;      -- the deleted row's id (its column named by the trigger)
BEGIN
    DELETE FROM wanted_extras WHERE kind = TG_ARGV[0] AND ref = gone;
    DELETE FROM wanted_prices WHERE kind = TG_ARGV[0] AND ref = gone;
    RETURN OLD;
END $$;

DROP TRIGGER IF EXISTS wishlist_drop_wanted ON wishlist;
CREATE TRIGGER wishlist_drop_wanted AFTER DELETE ON wishlist FOR EACH ROW EXECUTE FUNCTION drop_wanted_extras('wish', 'wish_id');
DROP TRIGGER IF EXISTS models_drop_wanted ON models;
CREATE TRIGGER models_drop_wanted AFTER DELETE ON models FOR EACH ROW EXECUTE FUNCTION drop_wanted_extras('model', 'model_id');
DROP TRIGGER IF EXISTS board_games_drop_wanted ON board_games;
CREATE TRIGGER board_games_drop_wanted AFTER DELETE ON board_games FOR EACH ROW EXECUTE FUNCTION drop_wanted_extras('game', 'game_id');
DROP TRIGGER IF EXISTS gear_drop_wanted ON gear;
CREATE TRIGGER gear_drop_wanted AFTER DELETE ON gear FOR EACH ROW EXECUTE FUNCTION drop_wanted_extras('gear', 'gear_id');
DROP TRIGGER IF EXISTS garden_items_drop_wanted ON garden_items;
CREATE TRIGGER garden_items_drop_wanted AFTER DELETE ON garden_items FOR EACH ROW EXECUTE FUNCTION drop_wanted_extras('garden', 'item_id');

-- Anything already left behind (none in prod when this was written).
DELETE FROM wanted_extras e WHERE NOT EXISTS (
    SELECT 1 FROM wishlist WHERE e.kind = 'wish' AND wish_id = e.ref UNION ALL
    SELECT 1 FROM models WHERE e.kind = 'model' AND model_id = e.ref UNION ALL
    SELECT 1 FROM board_games WHERE e.kind = 'game' AND game_id = e.ref UNION ALL
    SELECT 1 FROM gear WHERE e.kind = 'gear' AND gear_id = e.ref UNION ALL
    SELECT 1 FROM garden_items WHERE e.kind = 'garden' AND item_id = e.ref);
DELETE FROM wanted_prices p WHERE NOT EXISTS (
    SELECT 1 FROM wishlist WHERE p.kind = 'wish' AND wish_id = p.ref UNION ALL
    SELECT 1 FROM models WHERE p.kind = 'model' AND model_id = p.ref UNION ALL
    SELECT 1 FROM board_games WHERE p.kind = 'game' AND game_id = p.ref UNION ALL
    SELECT 1 FROM gear WHERE p.kind = 'gear' AND gear_id = p.ref UNION ALL
    SELECT 1 FROM garden_items WHERE p.kind = 'garden' AND item_id = p.ref);
