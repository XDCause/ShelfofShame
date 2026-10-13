-- Lifetime spend: remember the price with every stock change, so what you paid is kept even
-- after a price edit or after the item is removed from the inventory.
--
-- Spend = purchases (added, bought, bought (wishlist), starting stock, import) x unit_price,
-- minus Undo of a purchase. See GET /api/spending.
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\12_spend.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS unit_price NUMERIC(10, 2);

CREATE OR REPLACE FUNCTION log_stock_movement() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    reason  TEXT := NULLIF(current_setting('app.stock_reason', true), '');
    old_qty INT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- The row is gone, so supply_id can't point at it any more.
        INSERT INTO stock_movements (supply_id, item_name, change, qty_after, reason, unit_price)
        VALUES (NULL, OLD.name, -OLD.qty_on_hand, 0, COALESCE(reason, 'deleted'), OLD.unit_price);
        RETURN OLD;
    END IF;

    IF TG_OP = 'INSERT' THEN
        old_qty := 0;
    ELSE
        old_qty := OLD.qty_on_hand;
    END IF;

    IF NEW.qty_on_hand <> old_qty OR TG_OP = 'INSERT' THEN
        INSERT INTO stock_movements (supply_id, item_name, change, qty_after, reason, unit_price)
        VALUES (NEW.supply_id, NEW.name, NEW.qty_on_hand - old_qty, NEW.qty_on_hand,
                COALESCE(reason, CASE WHEN TG_OP = 'INSERT' THEN 'added' ELSE 'manual' END),
                NEW.unit_price);
    END IF;
    RETURN NEW;
END;
$$;

-- History from before this file: use the item's current price (the best we know).
UPDATE stock_movements m SET unit_price = s.unit_price
FROM supplies s
WHERE m.supply_id = s.supply_id AND m.unit_price IS NULL;

COMMIT;
