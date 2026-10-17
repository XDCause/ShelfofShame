-- Gardening (2026-10-18): where your Bunnings store keeps an item ("Aisle 35, Bay 8"), as the Bunnings button read it
-- from the product page with your store chosen. Idempotent.
ALTER TABLE garden_items ADD COLUMN IF NOT EXISTS store_aisle text;
