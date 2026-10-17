"""Database connection and shared rules, used by every part of the API."""
import atexit
import os
import threading
from contextlib import contextmanager

from fastapi import HTTPException
from psycopg import errors, sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Inside Docker the database is reachable by its service name "db" on Postgres's own port 5432.
# (5433 is only the port published to your Windows host.)
CONNINFO = make_conninfo(
    host=os.environ.get("DB_HOST", "db"),
    port=os.environ.get("DB_PORT", "5432"),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)

# Must match the CHECK constraints in db/init/*.sql.
PAINT_TYPES = ["Acrylic", "Lacquer", "Enamel", "Water-based", "Oil", "Alcohol-based", "N/A"]
FINISHES = ["Flat / Matt", "Satin", "Semi-gloss", "Gloss", "Metallic", "Clear", "Pearl",
            "Fluorescent", "N/A"]
CONDITIONS = ["Sealed", "Opened", "Half used", "Nearly empty", "Empty", "Dried out"]
PRIORITIES = ["High", "Normal", "Low"]
MODEL_STATUSES = ["Wanted", "In stash", "In progress", "On hold", "Finished", "Gone"]
# Each hobby's build steps in order (db/init/16_hobbies.sql); a model's stage = the last one done.
# Each hobby's build steps, in order (db/init/36_build_complete.sql must match). Every build ends at
# Complete; the steps in between can be skipped (models.skipped_steps), never the first.
STAGES = {
    "Scale model": ["Built", "Primed", "Painted", "Decals", "Weathered", "Complete"],
    "Warhammer": ["Built", "Primed", "Painted", "Based", "Complete"],
    "Gundam": ["Built", "Panel lined", "Decals", "Top coat", "Complete"],
}
HOBBIES = list(STAGES)
# Who usually makes each hobby's kits: a new Warhammer / Gundam model starts with that brand.
HOBBY_BRANDS = {"Warhammer": "Games Workshop", "Gundam": "Bandai"}
# Suggestions for the Grade field, with the usual scale for each.
GUNDAM_GRADES = {"EG": "1/144", "HG": "1/144", "RG": "1/144", "FM": "1/100", "MG": "1/100",
                 "RE/100": "1/100", "PG": "1/60", "SD": None}

# The hobby modules (web/src/modules/); a calendar event can belong to one (db/init/20_calendar.sql).
MODULE_IDS = ["models", "boardgames", "volleyball", "videogames", "chess", "reading", "car", "travel", "shooting", "hiking",
              "gardening"]   # 53 / 56 / 61 / 63 / 66
REPEATS = ["never", "weekly", "fortnightly"]
MOODS = ["great", "good", "okay", "meh", "rough"]                              # 25_mood.sql, best first
GAME_STATUSES = ["Owned", "To sell", "Wanted", "Borrowed", "Played elsewhere", "Gone"]   # 21 / 47 / 54_board_game_elsewhere.sql
GEAR_CONDITIONS = ["Wanted", "New", "Good", "Worn", "Needs replacing", "Retired"]   # 22_volleyball.sql, 50_gear_wanted.sql
GEAR_HOBBIES = ["volleyball", "hiking"]                                          # 65_hiking_gear.sql
VOLLEYBALL_KINDS = ["Game", "Training", "Social", "Tournament"]

# Friendly messages for database rule violations, keyed by constraint name.
CONSTRAINT_MESSAGES = {
    "supplies_brand_code_uq": "An item with that brand and product code already exists.",
    "supplies_qty_on_hand_check": "Quantity can't go below 0.",
    "wishlist_brand_code_uq": "That item is already on your wishlist.",
    "wishlist_qty_wanted_check": "Quantity wanted must be at least 1.",
    "product_info_barcode_uq": "That barcode is already linked to a different item.",
    "model_sessions_running_uq": "The timer is already running for this model.",
    "model_sessions_order_check": "A session can't end before it starts.",
    "price_guide_condition_check": "A price rule needs a name to match, a paint type or a size.",
    "models_stage_check": "That build step isn't one of this hobby's steps.",
    "models_figures_check": "Minis done must be between 0 and the number in the box.",
    "calendar_events_until_check": "It can't stop repeating before it starts.",
    "calendar_events_time_check": "The end time must be after the start time.",
    "board_games_players_check": "Most players can't be fewer than fewest players.",
    "volleyball_videos_url_check": "A video link must start with http:// or https://.",
    "hikes_gpx_hash_uq": "That GPX file has already been imported.",
    "hikes_time_check": "A hike can't end before it starts.",
    "hikes_trail_url_check": "A trail link must start with http:// or https://.",
    "gear_hobby_check": "Gear can only be for volleyball or hiking.",
    "garden_items_bunnings_uq": "That Bunnings product is already in your garden supplies.",
    "garden_logs_about_check": "Say what it's about: a plant, a container or a space.",
    "garden_plantings_harvest_check": "The harvest can't end before it starts.",
}


def stock_reason(conn, reason: str):
    """Label the quantity changes in this transaction for the stock history trigger
    (db/init/06_stock_history.sql). Unlabelled changes are recorded as 'manual'."""
    conn.execute("SELECT set_config('app.stock_reason', %s, true)", (reason,))


def insert_row(conn, table: str, data: dict, returning: str):
    """INSERT one row from a dict of column -> value; returns the `returning` column's value."""
    query = sql.SQL("INSERT INTO {t} ({cols}) VALUES ({vals}) RETURNING {r}").format(
        t=sql.Identifier(table), r=sql.Identifier(returning),
        cols=sql.SQL(", ").join(map(sql.Identifier, data)),
        vals=sql.SQL(", ").join(map(sql.Placeholder, data)))
    return conn.execute(query, data).fetchone()[returning]


def update_row(conn, table: str, id_col: str, row_id, data: dict) -> int:
    """UPDATE the given columns of one row; returns how many rows changed (0 = no such row)."""
    if not data:
        return 1
    query = sql.SQL("UPDATE {t} SET {sets} WHERE {id} = {rid}").format(
        t=sql.Identifier(table), id=sql.Identifier(id_col), rid=sql.Placeholder("_row_id"),
        sets=sql.SQL(", ").join(sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder(k))
                                for k in data))
    return conn.execute(query, {**data, "_row_id": row_id}).rowcount


def tidy_text(data: dict, required=("name", "title")) -> dict:
    """Trim every text value; blank text means "not set" (None). Required ones stay "" so the
    table's CHECK rejects them with a clear message."""
    return {k: (v.strip() or ("" if k in required else None)) if isinstance(v, str) else v
            for k, v in data.items()}


def found(row, what: str):
    """The row, or a 404 saying what wasn't found."""
    if row is None:
        raise HTTPException(404, f"{what} not found.")
    return row


def brand_id(conn, name: str) -> int | None:
    row = conn.execute("SELECT brand_id FROM brands WHERE name = %s", (name,)).fetchone()
    return row["brand_id"] if row else None


def ensure_brand(conn, name: str) -> int:
    """The brand's id, adding it first if it's new (brands are only added once they're used)."""
    conn.execute("INSERT INTO brands (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
    return brand_id(conn, name)


# Connections are kept open and lent out per request: opening a new one costs ~6 ms, a query on
# an open one ~0.1 ms, and Home alone makes about ten requests. Opened on first use.
# Each connection is checked (a quick round trip) before it's lent out, so one left over from
# before a database restart is replaced instead of failing the request.
POOL = ConnectionPool(CONNINFO, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=False,
                      check=ConnectionPool.check_connection)
_opening = threading.Lock()
atexit.register(POOL.close)     # close its connections and threads on the way out (quick restarts)


@contextmanager
def db():
    """A pooled connection and one transaction per request: commits on success, rolls back on error.

    Database errors are turned into HTTP errors the front end can show to the user.
    """
    try:
        if POOL.closed:
            with _opening:              # requests run in threads: open it once
                if POOL.closed:
                    POOL.open(wait=True)
        with POOL.connection() as conn:
            yield conn
    except errors.UniqueViolation as e:
        raise HTTPException(409, CONSTRAINT_MESSAGES.get(e.diag.constraint_name,
                                                         "That name already exists."))
    except errors.ForeignKeyViolation as e:
        if "still referenced" in (e.diag.message_detail or ""):
            raise HTTPException(409, "It's still in use, so it can't be removed.")
        raise HTTPException(422, "That brand, category, location or model doesn't exist.")
    except (errors.CheckViolation, errors.NotNullViolation) as e:
        raise HTTPException(422, CONSTRAINT_MESSAGES.get(e.diag.constraint_name,
                                                         e.diag.message_primary))
