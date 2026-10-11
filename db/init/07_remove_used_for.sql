-- App refresh (2026-10-11): "Used for / project" removed - supplies.used_for and the wishlist's
-- for_project that fed it. Both were empty when this ran.
--
-- Idempotent: safe on a fresh database (docker init) and on the existing one:
--   Get-Content db\init\07_remove_used_for.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

-- The view lists used_for, so Postgres won't drop the column while it exists. Drop the view,
-- drop the column, then recreate the view without it (otherwise identical to 01_schema.sql).
DROP VIEW IF EXISTS v_supplies;

ALTER TABLE supplies DROP COLUMN IF EXISTS used_for;
ALTER TABLE wishlist DROP COLUMN IF EXISTS for_project;

CREATE VIEW v_supplies AS
SELECT
    s.supply_id,
    'SUP-' || lpad(s.supply_id::text, 4, '0') AS item_ref,
    b.name  AS brand,
    s.product_code,
    s.name,
    c.name  AS category,
    s.paint_type,
    s.finish,
    s.size,
    s.qty_on_hand,
    s.reorder_at,
    CASE
        WHEN s.qty_on_hand <= 0            THEN 'Out'
        WHEN s.qty_on_hand <= s.reorder_at THEN 'Low'
        ELSE 'OK'
    END AS stock_status,
    s.condition,
    s.unit_price,
    s.qty_on_hand * s.unit_price AS total_value,
    s.purchase_date,
    s.purchased_from,
    l.name  AS location,
    s.notes,
    s.created_at,
    s.updated_at
FROM supplies s
JOIN      categories        c ON c.category_id = s.category_id
LEFT JOIN brands            b ON b.brand_id    = s.brand_id
LEFT JOIN storage_locations l ON l.location_id = s.location_id;

COMMIT;
