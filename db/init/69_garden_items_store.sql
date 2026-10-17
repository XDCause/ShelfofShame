-- Garden supplies: the Bunnings store a price and stock came from (the "Send to Off the Clock" button sends
-- what your browser shows for your chosen store - plants are sold regionally), and its stock there. Idempotent.
ALTER TABLE garden_items ADD COLUMN IF NOT EXISTS store_name text;
ALTER TABLE garden_items ADD COLUMN IF NOT EXISTS store_code text;
ALTER TABLE garden_items ADD COLUMN IF NOT EXISTS stock text;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'garden_items_stock_check') THEN
        ALTER TABLE garden_items ADD CONSTRAINT garden_items_stock_check
            CHECK (stock IN ('In stock', 'Low stock', 'Out of stock', 'Not sold at this store'));
    END IF;
END $$;
