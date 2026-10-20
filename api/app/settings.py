"""Settings: the default shop, your price guide, and backups.

Backups are the same files backup.ps1 makes (pg_dump custom format, hobby_inventory_<time>.dump,
newest 14 kept, logged to backup.log): the backups folder is shared with this container.
"""
import os
import re
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import PAINT_TYPES, db, found, insert_row, update_row

router = APIRouter(prefix="/api", tags=["settings"])

# ---------------------------------------------------------------------------
# Settings (key -> value)
# ---------------------------------------------------------------------------
# your_name: Home says "Good morning, <name>". banner_pictures: "on" shows the Picture button on every banner (off by
# default - it's clutter once your pictures are chosen; pictures already chosen show either way).
DEFAULTS = {"default_shop": "Hobbyrama", "your_name": None, "banner_pictures": "off"}


class SettingsPatch(BaseModel):
    default_shop: str | None = Field(None, max_length=100)
    your_name: str | None = Field(None, max_length=40)
    banner_pictures: Literal["on", "off"] | None = None


def get_setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else DEFAULTS.get(key)


@router.get("/settings")
def read_settings():
    with db() as conn:
        return {key: get_setting(conn, key) for key in DEFAULTS}


@router.patch("/settings")
def change_settings(body: SettingsPatch):
    with db() as conn:
        for key, value in body.model_dump(exclude_unset=True).items():
            value = (value or "").strip() or None
            conn.execute("INSERT INTO settings (key, value) VALUES (%s, %s) "
                         "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, value))
        return {key: get_setting(conn, key) for key in DEFAULTS}


# ---------------------------------------------------------------------------
# Price guide: your usual prices
# ---------------------------------------------------------------------------
class PriceRuleIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    title_contains: str | None = None
    paint_type: str | None = None
    size: str | None = None
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    sort_order: int = 0


class PriceRulePatch(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=100)
    title_contains: str | None = None
    paint_type: str | None = None
    size: str | None = None
    price: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    sort_order: int | None = None


def clean_rule(data: dict) -> dict:
    """Blank conditions mean "any"; paint type must be one of the usual ones."""
    for key in ("title_contains", "paint_type", "size"):
        if key in data:
            data[key] = (data[key] or "").strip() or None
    if data.get("paint_type") and data["paint_type"] not in PAINT_TYPES:
        raise HTTPException(422, f"Paint type must be one of: {', '.join(PAINT_TYPES)}.")
    return data


def price_for(conn, title: str | None, guess: dict) -> Decimal | None:
    """Your usual price for a product, from the first price-guide rule that fits it
    (every condition the rule has must match: name contains / paint type / size)."""
    rules = conn.execute("SELECT * FROM price_guide ORDER BY sort_order, rule_id").fetchall()
    name = (title or guess.get("name") or "").upper()
    for r in rules:
        if r["title_contains"] and r["title_contains"].upper() not in name:
            continue
        if r["paint_type"] and r["paint_type"] != guess.get("paint_type"):
            continue
        if r["size"] and r["size"].replace(" ", "").lower() != (guess.get("size") or "").lower():
            continue
        return r["price"]
    return None


@router.get("/price-guide")
def list_price_rules():
    with db() as conn:
        return conn.execute("SELECT * FROM price_guide ORDER BY sort_order, rule_id").fetchall()


@router.post("/price-guide", status_code=201)
def add_price_rule(body: PriceRuleIn):
    with db() as conn:
        rule_id = insert_row(conn, "price_guide", clean_rule(body.model_dump()), "rule_id")
        return conn.execute("SELECT * FROM price_guide WHERE rule_id = %s", (rule_id,)).fetchone()


@router.patch("/price-guide/{rule_id}")
def change_price_rule(rule_id: int, body: PriceRulePatch):
    with db() as conn:
        update_row(conn, "price_guide", "rule_id", rule_id, clean_rule(body.model_dump(exclude_unset=True)))
        return found(conn.execute("SELECT * FROM price_guide WHERE rule_id = %s", (rule_id,)).fetchone(),
                     "Price rule")


@router.delete("/price-guide/{rule_id}", status_code=204)
def delete_price_rule(rule_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM price_guide WHERE rule_id = %s RETURNING rule_id", (rule_id,)).fetchone(),
              "Price rule")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/backups"))
BACKUP_NAME = re.compile(r"^hobby_inventory_\d{8}_\d{6}\.dump$")
KEEP = 14


def _log(message: str):
    with open(BACKUP_DIR / "backup.log", "a", encoding="ascii", errors="replace") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}\n")


def _backups() -> list[Path]:
    return sorted((p for p in BACKUP_DIR.glob("hobby_inventory_*.dump") if BACKUP_NAME.match(p.name)),
                  reverse=True)


@router.get("/backups")
def list_backups():
    """Your backups, newest first, and the last lines of the backup log."""
    if not BACKUP_DIR.is_dir():
        return {"available": False, "backups": [], "log": []}
    log = BACKUP_DIR / "backup.log"
    lines = log.read_text(encoding="ascii", errors="replace").splitlines()[-5:] if log.exists() else []
    return {"available": True, "keep": KEEP, "log": lines[::-1],
            "backups": [{"name": p.name, "size": p.stat().st_size,
                         "created_at": datetime.strptime(p.name[16:31], "%Y%m%d_%H%M%S").isoformat()}
                        for p in _backups()]}


@router.post("/backups", status_code=201)
def back_up_now():
    """Back up everything now (same as backup.ps1), then keep only the newest 14."""
    if not BACKUP_DIR.is_dir():
        raise HTTPException(503, "The backups folder isn't connected to the API container.")
    name = f"hobby_inventory_{datetime.now():%Y%m%d_%H%M%S}.dump"
    env = {**os.environ, "PGPASSWORD": os.environ["POSTGRES_PASSWORD"]}
    done = subprocess.run(
        ["pg_dump", "-h", os.environ.get("DB_HOST", "db"), "-p", os.environ.get("DB_PORT", "5432"),
         "-U", os.environ["POSTGRES_USER"], "-d", os.environ["POSTGRES_DB"], "-Fc", "-f", str(BACKUP_DIR / name)],
        env=env, capture_output=True, text=True, timeout=300)
    if done.returncode != 0:
        problem = (done.stderr.strip().splitlines() or ["pg_dump returned an error"])[-1]
        _log(f"FAILED (from the app): {problem}")
        raise HTTPException(500, f"The backup failed: {problem}")
    size = (BACKUP_DIR / name).stat().st_size
    _log(f"OK: {name} ({round(size / 1024)} KB) - from the app")
    for old in _backups()[KEEP:]:
        old.unlink()
        _log(f"Removed old backup {old.name}")
    return {"name": name, "size": size}


@router.get("/backups/{name}")
def download_backup(name: str):
    """Download one backup file (to keep a copy somewhere other than this PC)."""
    path = BACKUP_DIR / name
    if not BACKUP_NAME.match(name) or not path.is_file():
        raise HTTPException(404, "No backup with that name.")
    return FileResponse(path, media_type="application/octet-stream", filename=name)
