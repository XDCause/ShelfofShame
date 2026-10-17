-- Gardening (an apartment garden: balcony, windowsills, indoor shelves). Idempotent.
--
--   garden_settings    one row: your climate zone (for what to sow when) and where you are (weather tips)
--   garden_spaces      a balcony, a windowsill, a shelf under a grow light: its size (for the layout), which way
--                      its open side faces, hours of sun, rain / wind, and how much weight it can hold
--   garden_containers  pots, troughs, grow bags, a worm farm... placed on a space's layout (x / y / size in cm)
--   garden_guides      what to know about each plant (sun, water, pot size, days to harvest, sowing months per
--                      climate zone, tips) - written for this app (68_garden_guides.sql), and your own additions
--   garden_plantings   a plant (or a row of seedlings) in a container: stage, dates, watering / feeding rhythm
--   garden_logs        what happened: notes, watering, feeding, harvests (amount), problems, measurements
--   garden_photos      photos on a log (a plant's photo timeline)
--   garden_tasks       your own reminders, once or repeating (watering / feeding due come from the plantings)
--   garden_items       supplies and the seed bank: potting mix, fertiliser, pots, seeds... (Bunnings links)
BEGIN;

CREATE TABLE IF NOT EXISTS garden_settings (
    id          integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    climate     text NOT NULL DEFAULT 'Subtropical' CHECK (climate IN ('Tropical', 'Subtropical', 'Temperate', 'Cool', 'Arid')),
    place_name  text,
    lat         double precision CHECK (lat BETWEEN -90 AND 90),
    lon         double precision CHECK (lon BETWEEN -180 AND 180),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO garden_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS garden_spaces (
    space_id     serial PRIMARY KEY,
    name         text NOT NULL CHECK (btrim(name) <> ''),
    kind         text NOT NULL DEFAULT 'Balcony'
                 CHECK (kind IN ('Balcony', 'Windowsill', 'Indoor', 'Shelf', 'Grow tent', 'Courtyard', 'Rooftop', 'Community plot')),
    width_cm     integer NOT NULL DEFAULT 300 CHECK (width_cm BETWEEN 20 AND 5000),
    depth_cm     integer NOT NULL DEFAULT 150 CHECK (depth_cm BETWEEN 20 AND 5000),
    open_side    text NOT NULL DEFAULT 'top' CHECK (open_side IN ('top', 'right', 'bottom', 'left')),  -- the railing / window on the plan
    facing       text CHECK (facing IN ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')),                  -- which way that side looks
    sun_hours    numeric(3, 1) CHECK (sun_hours BETWEEN 0 AND 16),
    covered      boolean NOT NULL DEFAULT true,           -- false = rain falls on it
    wind         text NOT NULL DEFAULT 'Some wind' CHECK (wind IN ('Sheltered', 'Some wind', 'Windy')),
    grow_light   boolean NOT NULL DEFAULT false,
    light_hours  numeric(3, 1) CHECK (light_hours BETWEEN 0 AND 24),
    max_load_kg  integer CHECK (max_load_kg > 0),
    notes        text,
    sort         integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS garden_containers (
    container_id  serial PRIMARY KEY,
    space_id      integer NOT NULL REFERENCES garden_spaces ON DELETE RESTRICT,
    name          text NOT NULL CHECK (btrim(name) <> ''),
    kind          text NOT NULL DEFAULT 'Pot' CHECK (kind IN ('Pot', 'Trough', 'Planter box', 'Grow bag', 'Hanging basket',
                  'Vertical planter', 'Self-watering pot', 'Raised planter', 'Hydroponic', 'Seed tray', 'Worm farm', 'Bokashi bin',
                  'Compost')),
    shape         text NOT NULL DEFAULT 'round' CHECK (shape IN ('round', 'rect')),
    x_cm          integer NOT NULL DEFAULT 10 CHECK (x_cm >= 0),
    y_cm          integer NOT NULL DEFAULT 10 CHECK (y_cm >= 0),
    width_cm      integer NOT NULL DEFAULT 30 CHECK (width_cm BETWEEN 5 AND 1000),
    depth_cm      integer NOT NULL DEFAULT 30 CHECK (depth_cm BETWEEN 5 AND 1000),
    level         text NOT NULL DEFAULT 'Floor' CHECK (level IN ('Floor', 'Stand', 'Shelf', 'Railing', 'Hanging', 'Wall')),
    volume_l      numeric(6, 1) CHECK (volume_l > 0),
    soil          text,
    self_watering boolean NOT NULL DEFAULT false,
    material      text,
    potted_on     date,
    notes         text,
    photo         bytea,
    photo_type    text,
    photo_updated timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS garden_containers_space_idx ON garden_containers (space_id);

CREATE TABLE IF NOT EXISTS garden_guides (
    guide_id          serial PRIMARY KEY,
    slug              text NOT NULL UNIQUE,
    name              text NOT NULL CHECK (btrim(name) <> ''),
    kind              text NOT NULL CHECK (kind IN ('Herb', 'Leafy green', 'Vegetable', 'Fruit', 'Microgreens', 'Flower',
                      'Houseplant', 'Succulent', 'Native')),
    sun               text NOT NULL CHECK (sun IN ('Full sun', 'Part sun', 'Shade', 'Bright indirect')),
    sun_hours_min     numeric(3, 1) NOT NULL DEFAULT 0,
    water             text NOT NULL CHECK (water IN ('Low', 'Medium', 'High')),
    water_every_days  integer NOT NULL DEFAULT 2 CHECK (water_every_days BETWEEN 1 AND 60),
    feed_every_days   integer CHECK (feed_every_days BETWEEN 1 AND 365),
    pot_min_l         numeric(5, 1),
    spacing_cm        integer,
    days_min          integer CHECK (days_min > 0),       -- sowing to first harvest (none for ornamentals)
    days_max          integer CHECK (days_max >= days_min),
    sow_how           text NOT NULL DEFAULT 'Either' CHECK (sow_how IN ('Seed', 'Seedling', 'Either', 'Cutting', 'Division')),
    sow_tropical      smallint[] NOT NULL DEFAULT '{}',
    sow_subtropical   smallint[] NOT NULL DEFAULT '{}',
    sow_temperate     smallint[] NOT NULL DEFAULT '{}',
    sow_cool          smallint[] NOT NULL DEFAULT '{}',
    sow_arid          smallint[] NOT NULL DEFAULT '{}',
    perennial         boolean NOT NULL DEFAULT false,
    companions        text,
    avoid             text,
    tips              text,
    harvest_tips      text,
    apartment_tips    text,
    pests             text,
    custom            boolean NOT NULL DEFAULT true,        -- false = one of the app's own (68_garden_guides.sql)
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS garden_items (
    item_id          serial PRIMARY KEY,
    name             text NOT NULL CHECK (btrim(name) <> ''),
    kind             text NOT NULL DEFAULT 'Other' CHECK (kind IN ('Seeds', 'Seedling', 'Potting mix', 'Fertiliser', 'Pot',
                     'Tool', 'Pest control', 'Grow light', 'Hydroponics', 'Watering', 'Other')),
    status           text NOT NULL DEFAULT 'Have' CHECK (status IN ('Have', 'Running low', 'Wanted', 'Used up')),
    qty              integer CHECK (qty >= 0),
    brand            text,
    guide_id         integer REFERENCES garden_guides ON DELETE SET NULL,   -- seeds: which plant
    sow_by           date,                                                 -- seeds: the packet's date
    notes            text,
    bunnings_item    text CHECK (bunnings_item ~ '^[0-9]{3,12}$'),
    url              text CHECK (url IS NULL OR url ~ '^https://'),
    price            numeric(10, 2) CHECK (price >= 0),
    price_checked_at timestamptz,
    rating           numeric(3, 2),
    reviews          integer,
    weight_kg        numeric(7, 2),
    category         text,
    description      text,
    how_to           text,
    photo            bytea,
    photo_type       text,
    photo_updated    timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT garden_items_bunnings_uq UNIQUE (bunnings_item)
);

CREATE TABLE IF NOT EXISTS garden_plantings (
    planting_id       serial PRIMARY KEY,
    container_id      integer REFERENCES garden_containers ON DELETE SET NULL,
    guide_id          integer REFERENCES garden_guides ON DELETE SET NULL,
    parent_id         integer REFERENCES garden_plantings ON DELETE SET NULL,   -- grown from a cutting of this one
    item_id           integer REFERENCES garden_items ON DELETE SET NULL,       -- the seed packet / seedling it came from
    name              text NOT NULL CHECK (btrim(name) <> ''),
    variety           text,
    source            text NOT NULL DEFAULT 'Seedling' CHECK (source IN ('Seed', 'Seedling', 'Cutting', 'Bought plant', 'Division')),
    stage             text NOT NULL DEFAULT 'Growing' CHECK (stage IN ('Planned', 'Sown', 'Sprouted', 'Seedling', 'Growing',
                      'Flowering', 'Fruiting', 'Harvesting', 'Dormant', 'Done', 'Died')),
    started_on        date NOT NULL DEFAULT current_date,
    quantity          integer NOT NULL DEFAULT 1 CHECK (quantity >= 1),
    water_every_days  integer CHECK (water_every_days BETWEEN 1 AND 60),
    feed_every_days   integer CHECK (feed_every_days BETWEEN 1 AND 365),
    last_watered_on   date,
    last_fed_on       date,
    harvest_from      date,
    harvest_to        date,
    bought_from       text,
    price             numeric(10, 2) CHECK (price >= 0),
    notes             text,
    ended_on          date,
    end_reason        text CHECK (end_reason IN ('Harvested out', 'Died', 'Gave away', 'Composted', 'Moved on')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT garden_plantings_harvest_check CHECK (harvest_to IS NULL OR harvest_from IS NULL OR harvest_to >= harvest_from)
);
CREATE INDEX IF NOT EXISTS garden_plantings_container_idx ON garden_plantings (container_id);

CREATE TABLE IF NOT EXISTS garden_logs (
    log_id        serial PRIMARY KEY,
    planting_id   integer REFERENCES garden_plantings ON DELETE CASCADE,
    container_id  integer REFERENCES garden_containers ON DELETE CASCADE,
    space_id      integer REFERENCES garden_spaces ON DELETE CASCADE,
    kind          text NOT NULL DEFAULT 'Note' CHECK (kind IN ('Note', 'Photo', 'Watered', 'Fed', 'Pruned', 'Harvested', 'Repotted',
                  'Moved', 'Pest', 'Problem', 'Treated', 'Sprouted', 'Flowered', 'Measured')),
    happened_on   date NOT NULL DEFAULT current_date,
    text          text,
    amount        numeric(10, 2),
    unit          text,
    tags          text[] NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT garden_logs_about_check CHECK (planting_id IS NOT NULL OR container_id IS NOT NULL OR space_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS garden_logs_planting_idx ON garden_logs (planting_id);
CREATE INDEX IF NOT EXISTS garden_logs_container_idx ON garden_logs (container_id);

CREATE TABLE IF NOT EXISTS garden_photos (
    photo_id    serial PRIMARY KEY,
    log_id      integer NOT NULL REFERENCES garden_logs ON DELETE CASCADE,
    image       bytea NOT NULL,
    image_type  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS garden_photos_log_idx ON garden_photos (log_id);

CREATE TABLE IF NOT EXISTS garden_tasks (
    task_id       serial PRIMARY KEY,
    title         text NOT NULL CHECK (btrim(title) <> ''),
    planting_id   integer REFERENCES garden_plantings ON DELETE CASCADE,
    container_id  integer REFERENCES garden_containers ON DELETE CASCADE,
    space_id      integer REFERENCES garden_spaces ON DELETE CASCADE,
    due_on        date NOT NULL DEFAULT current_date,
    repeat_days   integer CHECK (repeat_days BETWEEN 1 AND 365),
    notes         text,
    done_on       date,                      -- a repeating task moves its due_on on instead
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMIT;
