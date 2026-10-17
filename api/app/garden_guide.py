"""Gardening: the plant guide (the app's own entries from 68_garden_guides.sql, plus yours) and what to sow now.

    GET  /garden/guides?q=&kind=&season=now|next   the guide; each entry says if it's sowing time in your climate
                                                   this month / next, and which of your spaces get enough light
    GET  /garden/guides/{id}                        one, with the plants you've grown from it
    POST /garden/guides                             your own entry;  POST /garden/guides/{id}/copy  a copy to edit
    PATCH / DELETE /garden/guides/{id}              yours only (the app's own stay as written - copy one to change it)
    GET  /garden/sow-now                            this month's and next month's sowing list for your climate
"""
import re

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .garden import garden_settings, today

router = APIRouter(prefix="/api", tags=["gardening"])

# Must match db/init/67_garden.sql.
GUIDE_KINDS = ["Herb", "Leafy green", "Vegetable", "Fruit", "Microgreens", "Flower", "Houseplant", "Succulent", "Native"]
SUNS = ["Full sun", "Part sun", "Shade", "Bright indirect"]
WATERS = ["Low", "Medium", "High"]
SOW_HOW = ["Seed", "Seedling", "Either", "Cutting", "Division"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def _lit(values) -> str:
    return "^(" + "|".join(re.escape(v) for v in values) + ")$"


Months = list[int]


class GuideFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(GUIDE_KINDS))
    sun: str | None = Field(None, pattern=_lit(SUNS))
    sun_hours_min: float | None = Field(None, ge=0, le=16)
    water: str | None = Field(None, pattern=_lit(WATERS))
    water_every_days: int | None = Field(None, ge=1, le=60)
    feed_every_days: int | None = Field(None, ge=1, le=365)
    pot_min_l: float | None = Field(None, gt=0, le=5000)
    spacing_cm: int | None = Field(None, ge=1, le=1000)
    days_min: int | None = Field(None, ge=1, le=3000)
    days_max: int | None = Field(None, ge=1, le=3000)
    sow_how: str | None = Field(None, pattern=_lit(SOW_HOW))
    sow_tropical: Months | None = None
    sow_subtropical: Months | None = None
    sow_temperate: Months | None = None
    sow_cool: Months | None = None
    sow_arid: Months | None = None
    perennial: bool | None = None
    companions: str | None = Field(None, max_length=1000)
    avoid: str | None = Field(None, max_length=1000)
    tips: str | None = Field(None, max_length=5000)
    harvest_tips: str | None = Field(None, max_length=2000)
    apartment_tips: str | None = Field(None, max_length=2000)
    pests: str | None = Field(None, max_length=2000)


class GuideIn(GuideFields):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(pattern=_lit(GUIDE_KINDS))
    sun: str = Field(pattern=_lit(SUNS))
    water: str = Field(pattern=_lit(WATERS))


class GuidePatch(GuideFields):
    name: str | None = Field(None, min_length=1, max_length=120)


def _clean(data: dict) -> dict:
    data = tidy_text(data, required=("name",))
    for k in [k for k in data if k.startswith("sow_") and k != "sow_how"]:
        if data[k] is not None:
            if any(not 1 <= m <= 12 for m in data[k]):
                raise HTTPException(422, "Months are 1 to 12.")
            data[k] = sorted(set(data[k]))
    if data.get("days_min") and data.get("days_max") and data["days_max"] < data["days_min"]:
        raise HTTPException(422, "The longest time to harvest can't be shorter than the shortest.")
    return data


def light_of(space: dict) -> float:
    return float(space["sun_hours"] or 0) + (float(space["light_hours"] or 0) if space["grow_light"] else 0)


def annotate(guides: list[dict], climate: str, month: int, spaces: list[dict]) -> list[dict]:
    """Sowing time now / next month in your climate, and your spaces bright enough for it."""
    col = f"sow_{climate.lower()}"
    nxt = month % 12 + 1
    for g in guides:
        g["sow_now"] = month in (g[col] or [])
        g["sow_next"] = nxt in (g[col] or [])
        g["sow_months"] = g[col] or []
        need = float(g["sun_hours_min"] or 0)
        g["fits_spaces"] = [s["name"] for s in spaces if s["sun_hours"] is not None and light_of(s) >= need
                            or g["sun"] in ("Bright indirect", "Shade") and s["kind"] in ("Indoor", "Shelf", "Windowsill", "Grow tent")]
    return guides


GUIDE_SELECT = """SELECT g.*, g.sun_hours_min::float8 AS sun_hours_min, g.pot_min_l::float8 AS pot_min_l,
       (SELECT count(*) FROM garden_plantings p WHERE p.guide_id = g.guide_id AND p.stage NOT IN ('Done', 'Died')) AS growing,
       (SELECT count(*) FROM garden_plantings p WHERE p.guide_id = g.guide_id) AS grown
FROM garden_guides g"""


def _context(conn):
    s = garden_settings(conn)
    spaces = conn.execute("SELECT name, kind, sun_hours, grow_light, light_hours FROM garden_spaces").fetchall()
    return s["climate"], today(conn).month, spaces


@router.get("/garden/guides")
def list_guides(q: str | None = Query(None, max_length=100), kind: str | None = Query(None, pattern=_lit(GUIDE_KINDS)),
                season: str | None = Query(None, pattern="^(now|next)$")):
    with db() as conn:
        climate, month, spaces = _context(conn)
        rows = conn.execute(GUIDE_SELECT + """ WHERE (%(q)s::text IS NULL OR concat_ws(' ', g.name, g.kind, g.tips, g.apartment_tips)
                                ILIKE '%%' || %(q)s || '%%') AND (%(k)s::text IS NULL OR g.kind = %(k)s)
                            ORDER BY lower(g.name)""", {"q": (q or "").strip() or None, "k": kind}).fetchall()
    rows = annotate(rows, climate, month, spaces)
    if season:
        rows = [g for g in rows if g["sow_now" if season == "now" else "sow_next"]]
    return {"climate": climate, "month": MONTHS[month - 1], "guides": rows}


@router.get("/garden/sow-now")
def sow_now():
    """What to sow (or plant) this month and next in your climate, the ones that suit your spaces first."""
    with db() as conn:
        climate, month, spaces = _context(conn)
        rows = annotate(conn.execute(GUIDE_SELECT + " ORDER BY lower(g.name)").fetchall(), climate, month, spaces)
    order = lambda g: (not g["fits_spaces"] if spaces else False, g["name"].lower())  # noqa: E731
    # Houseplants and succulents can go in any month: not news for a "sow this month" list.
    rows = [g for g in rows if not (g["kind"] in ("Houseplant", "Succulent") and len(g["sow_months"]) == 12)]
    return {"climate": climate, "month": MONTHS[month - 1], "next_month": MONTHS[month % 12],
            "now": sorted([g for g in rows if g["sow_now"]], key=order),
            "next": sorted([g for g in rows if g["sow_next"] and not g["sow_now"]], key=order)}


def fetch_guide(conn, guide_id: int) -> dict:
    g = found(conn.execute(GUIDE_SELECT + " WHERE g.guide_id = %s", (guide_id,)).fetchone(), "Plant guide")
    climate, month, spaces = _context(conn)
    g = annotate([g], climate, month, spaces)[0]
    g["climate"] = climate
    g["plantings"] = conn.execute("""SELECT planting_id, name, variety, stage, started_on FROM garden_plantings
                                     WHERE guide_id = %s ORDER BY started_on DESC LIMIT 50""", (guide_id,)).fetchall()
    return g


@router.get("/garden/guides/{guide_id}")
def get_guide(guide_id: int):
    with db() as conn:
        return fetch_guide(conn, guide_id)


def _slug(conn, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "plant"
    slug, n = f"my-{base}", 1
    while conn.execute("SELECT 1 FROM garden_guides WHERE slug = %s", (slug,)).fetchone():
        n += 1
        slug = f"my-{base}-{n}"
    return slug


@router.post("/garden/guides", status_code=201)
def add_guide(body: GuideIn):
    data = _clean({k: v for k, v in body.model_dump().items() if v is not None})
    with db() as conn:
        data.update(slug=_slug(conn, data["name"]), custom=True)
        return fetch_guide(conn, insert_row(conn, "garden_guides", data, "guide_id"))


@router.post("/garden/guides/{guide_id}/copy", status_code=201)
def copy_guide(guide_id: int):
    """Your own copy of an entry (yours can be changed), named "... (mine)"."""
    with db() as conn:
        g = found(conn.execute("SELECT * FROM garden_guides WHERE guide_id = %s", (guide_id,)).fetchone(), "Plant guide")
        data = {k: v for k, v in g.items() if k not in ("guide_id", "slug", "custom", "created_at")}
        data["name"] = f"{g['name']} (mine)"[:120]
        data.update(slug=_slug(conn, data["name"]), custom=True)
        return fetch_guide(conn, insert_row(conn, "garden_guides", data, "guide_id"))


@router.patch("/garden/guides/{guide_id}")
def update_guide(guide_id: int, body: GuidePatch):
    data = _clean(body.model_dump(exclude_unset=True))
    for required in ("name", "kind", "sun", "water", "water_every_days", "sow_how", "perennial"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        g = found(conn.execute("SELECT custom, days_min, days_max FROM garden_guides WHERE guide_id = %s", (guide_id,)).fetchone(),
                  "Plant guide")
        if not g["custom"]:
            raise HTTPException(409, "That's one of the app's own entries - make a copy to change it.")
        lo, hi = data.get("days_min", g["days_min"]), data.get("days_max", g["days_max"])
        if lo and hi and hi < lo:
            raise HTTPException(422, "The longest time to harvest can't be shorter than the shortest.")
        update_row(conn, "garden_guides", "guide_id", guide_id, data)
        return fetch_guide(conn, guide_id)


@router.delete("/garden/guides/{guide_id}", status_code=204)
def delete_guide(guide_id: int):
    """Remove one of your entries (plants grown from it keep their details)."""
    with db() as conn:
        g = found(conn.execute("SELECT custom FROM garden_guides WHERE guide_id = %s", (guide_id,)).fetchone(), "Plant guide")
        if not g["custom"]:
            raise HTTPException(409, "The app's own entries can't be removed.")
        conn.execute("DELETE FROM garden_guides WHERE guide_id = %s", (guide_id,))
    return Response(status_code=204)
