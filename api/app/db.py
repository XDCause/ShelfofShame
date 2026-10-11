"""Database connection and shared rules, used by every part of the API."""
import os
from contextlib import contextmanager

import psycopg
from fastapi import HTTPException
from psycopg import errors
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

# Inside Docker the database is reachable by its service name "db" on Postgres's own port 5432.
# (5433 is only the port published to your Windows host.)
CONNINFO = make_conninfo(
    host=os.environ.get("DB_HOST", "db"),
    port=os.environ.get("DB_PORT", "5432"),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)

# Must match the CHECK constraints in db/init/01_schema.sql and 03_wishlist.sql.
PAINT_TYPES = ["Acrylic", "Lacquer", "Enamel", "Water-based", "Oil", "Alcohol-based", "N/A"]
FINISHES = ["Flat / Matt", "Satin", "Semi-gloss", "Gloss", "Metallic", "Clear", "Pearl",
            "Fluorescent", "N/A"]
CONDITIONS = ["Sealed", "Opened", "Half used", "Nearly empty", "Empty", "Dried out"]
PRIORITIES = ["High", "Normal", "Low"]

# Friendly messages for database rule violations, keyed by constraint name.
CONSTRAINT_MESSAGES = {
    "supplies_brand_code_uq": "An item with that brand and product code already exists.",
    "supplies_qty_on_hand_check": "Quantity can't go below 0.",
    "wishlist_brand_code_uq": "That item is already on your wishlist.",
    "wishlist_qty_wanted_check": "Quantity wanted must be at least 1.",
    "product_info_barcode_uq": "That barcode is already linked to a different item.",
}


def stock_reason(conn, reason: str):
    """Label the quantity changes in this transaction for the stock history trigger
    (db/init/06_stock_history.sql). Unlabelled changes are recorded as 'manual'."""
    conn.execute("SELECT set_config('app.stock_reason', %s, true)", (reason,))


@contextmanager
def db():
    """One connection + transaction per request: commits on success, rolls back on error.

    Database errors are turned into HTTP errors the front end can show to the user.
    """
    try:
        with psycopg.connect(CONNINFO, row_factory=dict_row) as conn:
            yield conn
    except errors.UniqueViolation as e:
        raise HTTPException(409, CONSTRAINT_MESSAGES.get(e.diag.constraint_name,
                                                         "That name already exists."))
    except errors.ForeignKeyViolation as e:
        if "still referenced" in (e.diag.message_detail or ""):
            raise HTTPException(409, "It's still in use by supplies or wishlist items.")
        raise HTTPException(422, "That brand, category or location doesn't exist.")
    except (errors.CheckViolation, errors.NotNullViolation) as e:
        raise HTTPException(422, CONSTRAINT_MESSAGES.get(e.diag.constraint_name,
                                                         e.diag.message_primary))
