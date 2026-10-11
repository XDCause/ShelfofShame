-- "Low" now also comes from condition (2026-10-11). Supplies are tracked one bottle at a time
-- (qty 1, reorder at 0), so quantity alone never shows Low. The real signal is the condition:
-- if your LAST one is Nearly empty, Empty or Dried out, it's Low.
--
--   Out: qty <= 0
--   Low: qty <= reorder_at,  or  qty = 1 and condition is Nearly empty / Empty / Dried out
--   OK:  otherwise
--
-- Same columns as before, so CREATE OR REPLACE works. Idempotent:
--   Get-Content db\init\08_condition_low.sql | docker exec -i hobby-inventory-db psql -U hobby -d hobby_inventory

BEGIN;

CREATE OR REPLACE VIEW v_supplies AS
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
        WHEN s.qty_on_hand = 1
         AND s.condition IN ('Nearly empty', 'Empty', 'Dried out') THEN 'Low'
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
