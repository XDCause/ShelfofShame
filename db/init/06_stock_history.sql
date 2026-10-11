-- Stock history: every change to a supply's quantity, recorded by the database itself.
--
-- A trigger does the logging, so it can't be bypassed: changes from the web app, the API, the
-- import script, or a manual edit in DBeaver are all recorded. The API says WHY with
--     SELECT set_config('app.stock_reason', 'used', true)   -- true = this transaction only
-- before its UPDATE; anything that doesn't set it is logged as 'manual'.
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\06_stock_history.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id SERIAL PRIMARY KEY,
    supply_id   INT REFERENCES supplies (supply_id) ON DELETE SET NULL,
    item_name   TEXT NOT NULL,          -- snapshot, so history still reads well after a delete
    change      INT NOT NULL,           -- +2 bought two, -1 used one
    qty_after   INT NOT NULL,
    reason      TEXT NOT NULL,          -- used, bought, edited, added, deleted, import, manual...
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS stock_movements_supply_idx ON stock_movements (supply_id, created_at DESC);

CREATE OR REPLACE FUNCTION log_stock_movement() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    reason  TEXT := NULLIF(current_setting('app.stock_reason', true), '');
    old_qty INT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- The row is gone, so supply_id can't point at it any more.
        INSERT INTO stock_movements (supply_id, item_name, change, qty_after, reason)
        VALUES (NULL, OLD.name, -OLD.qty_on_hand, 0, COALESCE(reason, 'deleted'));
        RETURN OLD;
    END IF;

    IF TG_OP = 'INSERT' THEN
        old_qty := 0;
    ELSE
        old_qty := OLD.qty_on_hand;
    END IF;

    IF NEW.qty_on_hand <> old_qty OR TG_OP = 'INSERT' THEN
        INSERT INTO stock_movements (supply_id, item_name, change, qty_after, reason)
        VALUES (NEW.supply_id, NEW.name, NEW.qty_on_hand - old_qty, NEW.qty_on_hand,
                COALESCE(reason, CASE WHEN TG_OP = 'INSERT' THEN 'added' ELSE 'manual' END));
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS supplies_log_stock ON supplies;
CREATE TRIGGER supplies_log_stock
    AFTER INSERT OR UPDATE OF qty_on_hand OR DELETE ON supplies
    FOR EACH ROW EXECUTE FUNCTION log_stock_movement();

-- First run on an existing database: record everyone's current stock as the starting point.
INSERT INTO stock_movements (supply_id, item_name, change, qty_after, reason, created_at)
SELECT supply_id, name, qty_on_hand, qty_on_hand, 'starting stock', created_at
FROM supplies
WHERE NOT EXISTS (SELECT 1 FROM stock_movements);

COMMIT;
