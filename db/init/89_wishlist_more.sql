-- The wishlist grows (2026-10-21, user: "do all 10" from a look at GiftList, Swym, Keepa / CamelCamelCamel, Qapital).
-- Things you want live in five places (wishlist = supplies, models / board_games / gear / garden_items marked Wanted), so
-- what's added here is keyed by (kind, ref): kind = 'wish' | 'model' | 'game' | 'gear' | 'garden', ref = that row's id.
--   wanted_extras   what it's for (a build or a goal), a target price ("tell me under $X"), money put aside for it,
--                   in stock or not at its shop (and when that was checked), the link it came from
--   wanted_prices   prices seen over time (you, the shop's catalogue, the weekly check)
--   wanted_history  what you bought from the list: when, where, the price you expected and paid
-- Idempotent.

CREATE TABLE IF NOT EXISTS wanted_extras (
    kind          TEXT NOT NULL CHECK (kind IN ('wish', 'model', 'game', 'gear', 'garden')),
    ref           INT NOT NULL,
    for_model_id  INT REFERENCES models (model_id) ON DELETE SET NULL,
    for_goal_id   INT REFERENCES goals (goal_id) ON DELETE SET NULL,
    target_price  NUMERIC(10, 2) CHECK (target_price >= 0),
    saved         NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (saved >= 0),
    in_stock      BOOLEAN,
    stock_checked TIMESTAMPTZ,
    link          TEXT CHECK (link IS NULL OR link ~ '^https?://'),
    PRIMARY KEY (kind, ref)
);

CREATE TABLE IF NOT EXISTS wanted_prices (
    price_id  SERIAL PRIMARY KEY,
    kind      TEXT NOT NULL CHECK (kind IN ('wish', 'model', 'game', 'gear', 'garden')),
    ref       INT NOT NULL,
    price     NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    source    TEXT NOT NULL DEFAULT 'you',          -- you, the shop's name, weekly check
    seen_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS wanted_prices_item ON wanted_prices (kind, ref, seen_at DESC);

CREATE TABLE IF NOT EXISTS wanted_history (
    history_id SERIAL PRIMARY KEY,
    kind       TEXT NOT NULL,
    ref        INT,                                 -- (what it became: a supply, the kit, the game...)
    name       TEXT NOT NULL,
    hobby      TEXT,
    shop       TEXT,
    expected   NUMERIC(10, 2),
    paid       NUMERIC(10, 2),
    wanted_on  DATE,
    bought_on  DATE NOT NULL DEFAULT current_date
);
CREATE INDEX IF NOT EXISTS wanted_history_bought ON wanted_history (bought_on DESC);
