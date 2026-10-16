-- Gear from a shop's product search (Blue Sky Athletics: Way of Wade shoes): which shop, its page,
-- its price, and its product number there. Idempotent.
ALTER TABLE gear ADD COLUMN IF NOT EXISTS shop_name TEXT;
ALTER TABLE gear ADD COLUMN IF NOT EXISTS shop_url TEXT CHECK (shop_url IS NULL OR shop_url ~ '^https://');
ALTER TABLE gear ADD COLUMN IF NOT EXISTS shop_price NUMERIC(10, 2) CHECK (shop_price >= 0);
ALTER TABLE gear ADD COLUMN IF NOT EXISTS shop_id TEXT CHECK (shop_id IS NULL OR shop_id ~ '^[0-9]+$');
