"""Gardening (a hobby module), built for an apartment: a balcony, windowsills, shelves under a grow light.

    settings    your climate zone (what to sow when) and where you are (weather tips; Open-Meteo)
    spaces      a balcony / windowsill / shelf: size, which way it faces, sun, rain, wind, weight limit;
                its layout = its containers placed in cm (x / y / width / depth), each with its plants
    containers  pots, troughs, grow bags, hanging baskets, worm farm...: size, litres, soil, level, photo
    plantings   a plant (or several) in a container: stage, dates, harvest window (from its guide), how often
                to water / feed (self-watering pots: half as often) and when it was last done; propagate a
                cutting from it; warnings when its space has too little sun or its pot is too small
    care        "watered" / "fed" for one plant, a container, a whole space, or everything due
    logs        notes, harvests (amount + unit), problems, measurements... each with photos (a photo timeline)
    tasks       your own reminders, once or repeating
    today       what needs water / feed, what's ready to pick, tasks due, and weather tips for the balcony
    harvests    every harvest, with totals per plant and per month
Logs, photos and tasks: garden_logs.py. Today, the summary and harvests: garden_today.py.
Plant guides and what to sow now: garden_guide.py. Supplies, seeds and Bunnings: garden_items.py.
"""
import re
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import openmeteo
from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["gardening"])

# Must match the CHECKs in db/init/67_garden.sql.
CLIMATES = ["Tropical", "Subtropical", "Temperate", "Cool", "Arid"]
SPACE_KINDS = ["Balcony", "Windowsill", "Indoor", "Shelf", "Grow tent", "Courtyard", "Rooftop", "Community plot"]
SIDES = ["top", "right", "bottom", "left"]
FACINGS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
WINDS = ["Sheltered", "Some wind", "Windy"]
CONTAINER_KINDS = ["Pot", "Trough", "Planter box", "Grow bag", "Hanging basket", "Vertical planter", "Self-watering pot",
                   "Raised planter", "Hydroponic", "Seed tray", "Worm farm", "Bokashi bin", "Compost"]
SHAPES = ["round", "rect"]
LEVELS = ["Floor", "Stand", "Shelf", "Railing", "Hanging", "Wall"]
SOURCES = ["Seed", "Seedling", "Cutting", "Bought plant", "Division"]
STAGES = ["Planned", "Sown", "Sprouted", "Seedling", "Growing", "Flowering", "Fruiting", "Harvesting", "Dormant", "Done", "Died"]
ENDED = ("Done", "Died")
END_REASONS = ["Harvested out", "Died", "Gave away", "Composted", "Moved on"]
LOG_KINDS = ["Note", "Photo", "Watered", "Fed", "Pruned", "Harvested", "Repotted", "Moved", "Pest", "Problem", "Treated",
             "Sprouted", "Flowered", "Measured"]
UNITS = ["g", "kg", "count", "bunch", "handful", "cm", "pH", "EC", "°C", "L"]
PROBLEM_TAGS = ["Aphids", "Whitefly", "Mealybugs", "Scale", "Spider mites", "Fungus gnats", "Caterpillars", "Snails / slugs",
                "Fruit fly", "Powdery mildew", "Rust", "Root rot", "Yellow leaves", "Brown tips", "Leggy", "Wilting",
                "Sunburn", "Bolting", "Birds", "Possums"]
# How old a plant usually is when it goes in, by how it started (seedlings from a nursery are ~3 weeks on).
HEAD_START = {"Seed": 0, "Seedling": 21, "Cutting": 14, "Bought plant": 30, "Division": 30}
KG_PER_LITRE = 1.0           # wet potting mix, roughly: what a balcony carries


def _lit(values) -> str:
    return "^(" + "|".join(re.escape(v) for v in values) + ")$"


# ---------------------------------------------------------------------------------------------
# Settings, lists
# ---------------------------------------------------------------------------------------------
class SettingsIn(BaseModel):
    climate: str | None = Field(None, pattern=_lit(CLIMATES))
    place_name: str | None = Field(None, max_length=120)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)


def garden_settings(conn) -> dict:
    return conn.execute("SELECT climate, place_name, lat, lon FROM garden_settings WHERE id = 1").fetchone()


@router.get("/garden/settings")
def get_settings():
    with db() as conn:
        return garden_settings(conn)


@router.put("/garden/settings")
def put_settings(body: SettingsIn):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    with db() as conn:
        if data:
            update_row(conn, "garden_settings", "id", 1, {**data})
            conn.execute("UPDATE garden_settings SET updated_at = now() WHERE id = 1")
        return garden_settings(conn)


@router.get("/garden/places")
def find_places(q: str = Query(..., min_length=2, max_length=80)):
    """Places matching a suburb / town name (Open-Meteo), to set where you are for weather tips."""
    try:
        return openmeteo.find_place(q.strip())
    except openmeteo.WeatherError as e:
        raise HTTPException(502, str(e))


@router.get("/garden/lists")
def lists():
    """Every choice list the forms use (the same as the database's rules)."""
    from .garden_guide import GUIDE_KINDS, SOW_HOW, SUNS, WATERS
    from .garden_items import ITEM_KINDS, ITEM_STATUSES
    return {"climates": CLIMATES, "space_kinds": SPACE_KINDS, "sides": SIDES, "facings": FACINGS, "winds": WINDS,
            "container_kinds": CONTAINER_KINDS, "shapes": SHAPES, "levels": LEVELS, "sources": SOURCES, "stages": STAGES,
            "end_reasons": END_REASONS, "log_kinds": LOG_KINDS, "units": UNITS, "problem_tags": PROBLEM_TAGS,
            "guide_kinds": GUIDE_KINDS, "suns": SUNS, "waters": WATERS, "sow_how": SOW_HOW,
            "item_kinds": ITEM_KINDS, "item_statuses": ITEM_STATUSES}


# ---------------------------------------------------------------------------------------------
# Plantings: the shared SELECT (due dates worked out in SQL; "today" is the database's)
# ---------------------------------------------------------------------------------------------
PLANTING_SELECT = """
SELECT p.planting_id, p.container_id, p.guide_id, p.parent_id, p.item_id, p.name, p.variety, p.source, p.stage, p.started_on,
       p.quantity, p.water_every_days, p.feed_every_days, p.last_watered_on, p.last_fed_on, p.harvest_from, p.harvest_to,
       p.bought_from, p.price, p.notes, p.ended_on, p.end_reason, p.created_at,
       c.name AS container_name, c.kind AS container_kind, c.self_watering, c.volume_l::float8 AS volume_l,
       s.space_id, s.name AS space_name, s.sun_hours::float8 AS sun_hours, s.grow_light, s.light_hours::float8 AS light_hours,
       s.covered, g.name AS guide_name, g.kind AS plant_kind, g.sun AS guide_sun, g.sun_hours_min::float8 AS sun_hours_min,
       g.pot_min_l::float8 AS pot_min_l,
       CASE WHEN p.stage IN ('Planned', 'Done', 'Died') OR p.water_every_days IS NULL THEN NULL
            ELSE COALESCE(p.last_watered_on + p.water_every_days * CASE WHEN c.self_watering THEN 2 ELSE 1 END, current_date)
       END AS water_due_on,
       CASE WHEN p.stage IN ('Planned', 'Done', 'Died', 'Dormant') OR p.feed_every_days IS NULL THEN NULL
            ELSE COALESCE(p.last_fed_on, p.started_on) + p.feed_every_days END AS feed_due_on,
       (p.stage NOT IN ('Planned', 'Done', 'Died') AND p.harvest_from IS NOT NULL AND p.harvest_from <= current_date) AS harvest_ready,
       current_date - p.started_on AS age_days,
       (SELECT '/api/garden/photos/' || ph.photo_id FROM garden_photos ph JOIN garden_logs l USING (log_id)
        WHERE l.planting_id = p.planting_id ORDER BY l.happened_on DESC, ph.photo_id DESC LIMIT 1) AS photo_url
FROM garden_plantings p
LEFT JOIN garden_containers c ON c.container_id = p.container_id
LEFT JOIN garden_spaces s ON s.space_id = c.space_id
LEFT JOIN garden_guides g ON g.guide_id = p.guide_id"""


def warnings_for(conn, p: dict) -> list[str]:
    """Why this plant may struggle where it is: too little light, too small a pot, out of season."""
    out = []
    if p["space_id"] is not None and p["sun_hours_min"]:
        light = (p["sun_hours"] or 0) + ((p["light_hours"] or 0) if p["grow_light"] else 0)
        if p["sun_hours"] is not None and light < p["sun_hours_min"]:
            out.append(f"{p['guide_name']} wants about {p['sun_hours_min']:g} h of sun; {p['space_name']} gets about {light:g} h.")
    if p["volume_l"] and p["pot_min_l"] and p["volume_l"] < p["pot_min_l"] * min(p["quantity"], 4) * 0.8:
        out.append(f"The pot is small for it: {p['volume_l']:g} L, and {p['guide_name']} likes {p['pot_min_l']:g} L or more"
                   + (" each." if p["quantity"] > 1 else "."))
    if p["guide_id"] and p["source"] in ("Seed", "Seedling") and p["stage"] in ("Planned", "Sown", "Sprouted", "Seedling"):
        climate = garden_settings(conn)["climate"]
        months = conn.execute(f"SELECT sow_{climate.lower()} AS m FROM garden_guides WHERE guide_id = %s",
                              (p["guide_id"],)).fetchone()["m"]
        if months and p["started_on"].month not in months:
            out.append(f"{p['started_on']:%B} isn't the usual time to start it in a {climate.lower()} climate - it may struggle or bolt.")
    return out


def fetch_planting(conn, planting_id: int) -> dict:
    p = found(conn.execute(PLANTING_SELECT + " WHERE p.planting_id = %s", (planting_id,)).fetchone(), "Plant")
    p["warnings"] = warnings_for(conn, p)
    p["logs"] = logs_for(conn, "planting_id", planting_id)
    p["harvested"] = conn.execute("""SELECT unit, sum(amount)::float8 AS amount, count(*) AS times FROM garden_logs
        WHERE planting_id = %s AND kind = 'Harvested' GROUP BY unit ORDER BY unit NULLS LAST""", (planting_id,)).fetchall()
    p["children"] = conn.execute("SELECT planting_id, name, stage FROM garden_plantings WHERE parent_id = %s ORDER BY started_on",
                                 (planting_id,)).fetchall()
    p["parent"] = conn.execute("SELECT planting_id, name FROM garden_plantings WHERE planting_id = %s",
                               (p["parent_id"],)).fetchone() if p["parent_id"] else None
    p["tasks"] = conn.execute(TASK_SELECT + " WHERE t.planting_id = %s AND t.done_on IS NULL ORDER BY t.due_on", (planting_id,)).fetchall()
    p["guide"] = conn.execute("SELECT * FROM garden_guides WHERE guide_id = %s", (p["guide_id"],)).fetchone() if p["guide_id"] else None
    return p


# ---------------------------------------------------------------------------------------------
# Spaces and their layout
# ---------------------------------------------------------------------------------------------
class SpaceFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(SPACE_KINDS))
    width_cm: int | None = Field(None, ge=20, le=5000)
    depth_cm: int | None = Field(None, ge=20, le=5000)
    open_side: str | None = Field(None, pattern=_lit(SIDES))
    facing: str | None = Field(None, pattern=_lit(FACINGS))
    sun_hours: float | None = Field(None, ge=0, le=16)
    covered: bool | None = None
    wind: str | None = Field(None, pattern=_lit(WINDS))
    grow_light: bool | None = None
    light_hours: float | None = Field(None, ge=0, le=24)
    max_load_kg: int | None = Field(None, gt=0, le=100000)
    notes: str | None = Field(None, max_length=5000)
    sort: int | None = None


class SpaceIn(SpaceFields):
    name: str = Field(min_length=1, max_length=120)


class SpacePatch(SpaceFields):
    name: str | None = Field(None, min_length=1, max_length=120)


SPACE_SELECT = """
SELECT s.*, s.sun_hours::float8 AS sun_hours, s.light_hours::float8 AS light_hours,
       (SELECT count(*) FROM garden_containers c WHERE c.space_id = s.space_id) AS containers,
       (SELECT count(*) FROM garden_plantings p JOIN garden_containers c USING (container_id)
        WHERE c.space_id = s.space_id AND p.stage NOT IN ('Done', 'Died')) AS plants,
       (SELECT round(COALESCE(sum(c.volume_l), 0) * %(kg)s)::int FROM garden_containers c WHERE c.space_id = s.space_id) AS load_kg
FROM garden_spaces s"""


def fetch_space(conn, space_id: int, layout: bool = True) -> dict:
    s = found(conn.execute(SPACE_SELECT + " WHERE s.space_id = %(id)s", {"kg": KG_PER_LITRE, "id": space_id}).fetchone(), "Space")
    if layout:
        s["containers"] = containers_in(conn, space_id)
        s["logs"] = logs_for(conn, "space_id", space_id)
    return s


def containers_in(conn, space_id: int) -> list[dict]:
    """The space's containers for the layout, each with its (current) plants and what they need."""
    rows = conn.execute(CONTAINER_SELECT + " WHERE c.space_id = %s ORDER BY c.y_cm, c.x_cm", (space_id,)).fetchall()
    plants = conn.execute(PLANTING_SELECT + " WHERE c.space_id = %s AND p.stage NOT IN ('Done', 'Died') ORDER BY p.started_on",
                          (space_id,)).fetchall()
    for c in rows:
        c["plantings"] = [p for p in plants if p["container_id"] == c["container_id"]]
    return rows


@router.get("/garden/spaces")
def list_spaces():
    with db() as conn:
        return conn.execute(SPACE_SELECT + " ORDER BY s.sort, s.space_id", {"kg": KG_PER_LITRE}).fetchall()


@router.post("/garden/spaces", status_code=201)
def add_space(body: SpaceIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        return fetch_space(conn, insert_row(conn, "garden_spaces", data, "space_id"))


@router.get("/garden/spaces/{space_id}")
def get_space(space_id: int):
    with db() as conn:
        return fetch_space(conn, space_id)


@router.patch("/garden/spaces/{space_id}")
def update_space(space_id: int, body: SpacePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "kind", "width_cm", "depth_cm", "open_side", "covered", "wind", "grow_light"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        fetch_space(conn, space_id, layout=False)
        update_row(conn, "garden_spaces", "space_id", space_id, data)
        return fetch_space(conn, space_id)


@router.delete("/garden/spaces/{space_id}", status_code=204)
def delete_space(space_id: int):
    with db() as conn:
        n = conn.execute("SELECT count(*) AS n FROM garden_containers WHERE space_id = %s", (space_id,)).fetchone()["n"]
        if n:
            raise HTTPException(409, f"It still has {n} container{'s' if n > 1 else ''} - move or remove them first.")
        found(conn.execute("DELETE FROM garden_spaces WHERE space_id = %s RETURNING space_id", (space_id,)).fetchone(), "Space")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------------------------
class ContainerFields(BaseModel):
    space_id: int | None = None
    kind: str | None = Field(None, pattern=_lit(CONTAINER_KINDS))
    shape: str | None = Field(None, pattern=_lit(SHAPES))
    x_cm: int | None = Field(None, ge=0, le=5000)
    y_cm: int | None = Field(None, ge=0, le=5000)
    width_cm: int | None = Field(None, ge=5, le=1000)
    depth_cm: int | None = Field(None, ge=5, le=1000)
    level: str | None = Field(None, pattern=_lit(LEVELS))
    volume_l: float | None = Field(None, gt=0, le=5000)
    soil: str | None = Field(None, max_length=120)
    self_watering: bool | None = None
    material: str | None = Field(None, max_length=80)
    potted_on: date | None = None
    notes: str | None = Field(None, max_length=5000)


class ContainerIn(ContainerFields):
    name: str = Field(min_length=1, max_length=120)
    space_id: int


class ContainerPatch(ContainerFields):
    name: str | None = Field(None, min_length=1, max_length=120)


CONTAINER_SELECT = """
SELECT c.container_id, c.space_id, c.name, c.kind, c.shape, c.x_cm, c.y_cm, c.width_cm, c.depth_cm, c.level,
       c.volume_l::float8 AS volume_l, c.soil, c.self_watering, c.material, c.potted_on, c.notes, c.created_at,
       s.name AS space_name,
       CASE WHEN c.photo IS NOT NULL THEN '/api/garden/containers/' || c.container_id || '/photo?v='
            || (extract(epoch FROM c.photo_updated) * 1000)::bigint END AS photo_url
FROM garden_containers c JOIN garden_spaces s ON s.space_id = c.space_id"""


def fetch_container(conn, container_id: int) -> dict:
    c = found(conn.execute(CONTAINER_SELECT + " WHERE c.container_id = %s", (container_id,)).fetchone(), "Container")
    c["plantings"] = conn.execute(PLANTING_SELECT + " WHERE p.container_id = %s ORDER BY p.stage IN ('Done', 'Died'), p.started_on DESC",
                                  (container_id,)).fetchall()
    c["logs"] = logs_for(conn, "container_id", container_id)
    return c


def fit_in_space(conn, data: dict, space_id: int):
    """Keep a container inside its space's plan (the layout can't drop it off the edge)."""
    s = conn.execute("SELECT width_cm, depth_cm FROM garden_spaces WHERE space_id = %s", (space_id,)).fetchone()
    if s is None:
        raise HTTPException(422, "That space doesn't exist.")
    for pos, size, limit in (("x_cm", "width_cm", s["width_cm"]), ("y_cm", "depth_cm", s["depth_cm"])):
        if data.get(size) is not None:
            data[size] = min(data[size], limit)
        if data.get(pos) is not None:
            data[pos] = max(0, min(data[pos], limit - (data.get(size) or 5)))


@router.get("/garden/containers")
def list_containers():
    """Every container (for "which pot?" pickers), by space."""
    with db() as conn:
        return conn.execute(CONTAINER_SELECT + " ORDER BY s.sort, s.space_id, lower(c.name)").fetchall()


@router.post("/garden/containers", status_code=201)
def add_container(body: ContainerIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    if data.get("kind") == "Self-watering pot":
        data["self_watering"] = True
    with db() as conn:
        fit_in_space(conn, data, data["space_id"])
        return fetch_container(conn, insert_row(conn, "garden_containers", data, "container_id"))


@router.get("/garden/containers/{container_id}")
def get_container(container_id: int):
    with db() as conn:
        return fetch_container(conn, container_id)


@router.patch("/garden/containers/{container_id}")
def update_container(container_id: int, body: ContainerPatch):
    """Change a container - or move / resize it on the layout (x_cm, y_cm, width_cm, depth_cm)."""
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "space_id", "kind", "shape", "x_cm", "y_cm", "width_cm", "depth_cm", "level", "self_watering"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        current = fetch_container(conn, container_id)
        space_id = data.get("space_id", current["space_id"])
        if any(k in data for k in ("x_cm", "y_cm", "width_cm", "depth_cm", "space_id")):
            sized = {k: data.get(k, current[k]) for k in ("x_cm", "y_cm", "width_cm", "depth_cm")}
            fit_in_space(conn, sized, space_id)
            data.update(sized)
        if "space_id" in data and data["space_id"] != current["space_id"]:
            for p in current["plantings"]:
                if p["stage"] not in ENDED:
                    insert_row(conn, "garden_logs", {"planting_id": p["planting_id"], "kind": "Moved",
                                                     "text": f"Moved with {current['name']} to {space_name(conn, space_id)}"}, "log_id")
        update_row(conn, "garden_containers", "container_id", container_id, data)
        return fetch_container(conn, container_id)


COPIED = ("space_id", "kind", "shape", "width_cm", "depth_cm", "level", "volume_l", "soil", "self_watering", "material")


def next_name(conn, name: str) -> str:
    """"Trough" -> "Trough 2" (or the next number free); a copy of "Trough 2" -> "Trough 3"."""
    base = re.sub(r"\s+\d+$", "", name).strip() or name
    taken = [r["name"] for r in conn.execute("SELECT name FROM garden_containers WHERE name = %s OR name ~ %s",
                                             (base, "^" + re.escape(base) + r" \d+$")).fetchall()]
    numbers = [int(n.rsplit(" ", 1)[1]) for n in taken if n != base] + [1]
    return f"{base} {max(numbers) + 1}"[:120]


@router.post("/garden/containers/{container_id}/copy", status_code=201)
def copy_container(container_id: int):
    """Another container just like this one (when you have two the same): its kind, size, level, mix and material,
    placed beside it on the layout, named "... 2". Its plants, notes, photo and history stay with the original."""
    with db() as conn:
        c = fetch_container(conn, container_id)
        s = conn.execute("SELECT width_cm, depth_cm FROM garden_spaces WHERE space_id = %s", (c["space_id"],)).fetchone()
        data = {k: c[k] for k in COPIED if c[k] is not None}
        gap = 5
        if c["x_cm"] + 2 * c["width_cm"] + gap <= s["width_cm"]:              # to its right
            data.update(x_cm=c["x_cm"] + c["width_cm"] + gap, y_cm=c["y_cm"])
        elif c["y_cm"] + 2 * c["depth_cm"] + gap <= s["depth_cm"]:            # below it
            data.update(x_cm=c["x_cm"], y_cm=c["y_cm"] + c["depth_cm"] + gap)
        else:                                                                 # no room: a little offset
            data.update(x_cm=c["x_cm"] + 10, y_cm=c["y_cm"] + 10)
        fit_in_space(conn, data, c["space_id"])
        data["name"] = next_name(conn, c["name"])
        return fetch_container(conn, insert_row(conn, "garden_containers", data, "container_id"))


def space_name(conn, space_id: int) -> str:
    row = conn.execute("SELECT name FROM garden_spaces WHERE space_id = %s", (space_id,)).fetchone()
    return row["name"] if row else "another space"


@router.delete("/garden/containers/{container_id}", status_code=204)
def delete_container(container_id: int):
    """Remove a container; its plants stay in your list (not in a pot) with their history."""
    with db() as conn:
        found(conn.execute("DELETE FROM garden_containers WHERE container_id = %s RETURNING container_id",
                           (container_id,)).fetchone(), "Container")
    return Response(status_code=204)


add_photo_routes(router, "/garden/containers", "garden_containers", "container_id", "Container")


# ---------------------------------------------------------------------------------------------
# Plantings
# ---------------------------------------------------------------------------------------------
class PlantingFields(BaseModel):
    container_id: int | None = None
    guide_id: int | None = None
    item_id: int | None = None
    variety: str | None = Field(None, max_length=120)
    source: str | None = Field(None, pattern=_lit(SOURCES))
    stage: str | None = Field(None, pattern=_lit(STAGES))
    started_on: date | None = None
    quantity: int | None = Field(None, ge=1, le=10000)
    water_every_days: int | None = Field(None, ge=1, le=60)
    feed_every_days: int | None = Field(None, ge=1, le=365)
    last_watered_on: date | None = None
    last_fed_on: date | None = None
    harvest_from: date | None = None
    harvest_to: date | None = None
    bought_from: str | None = Field(None, max_length=120)
    price: float | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=10000)
    ended_on: date | None = None
    end_reason: str | None = Field(None, pattern=_lit(END_REASONS))


class PlantingIn(PlantingFields):
    name: str | None = Field(None, max_length=120)      # empty: the guide's name


class PlantingPatch(PlantingFields):
    name: str | None = Field(None, min_length=1, max_length=120)


def from_guide(conn, data: dict) -> dict:
    """A guide's defaults for what wasn't given: the name, watering / feeding rhythm, the harvest window."""
    g = conn.execute("SELECT * FROM garden_guides WHERE guide_id = %s", (data["guide_id"],)).fetchone() if data.get("guide_id") else None
    if data.get("guide_id") and not g:
        raise HTTPException(422, "That plant guide doesn't exist.")
    if g:
        data.setdefault("name", g["name"])
        data.setdefault("water_every_days", g["water_every_days"])
        if g["feed_every_days"]:
            data.setdefault("feed_every_days", g["feed_every_days"])
        if g["days_min"] and "harvest_from" not in data:
            start = data.get("started_on") or conn.execute("SELECT current_date AS d").fetchone()["d"]
            ahead = HEAD_START.get(data.get("source") or "Seedling", 0)
            data["harvest_from"] = start + timedelta(days=max(7, g["days_min"] - ahead))
            data["harvest_to"] = start + timedelta(days=max(14, g["days_max"] - ahead))
    return data


@router.get("/garden/plantings")
def list_plantings(status: str = Query("current", pattern="^(current|past|all)$"), space_id: int | None = None,
                   q: str | None = Query(None, max_length=100)):
    """Your plants: current ones (not done or died), past ones, or all; by space; searched by name / variety / notes."""
    where = {"current": "p.stage NOT IN ('Done', 'Died')", "past": "p.stage IN ('Done', 'Died')", "all": "TRUE"}[status]
    with db() as conn:
        return conn.execute(PLANTING_SELECT + f""" WHERE {where} AND (%(space)s::int IS NULL OR s.space_id = %(space)s)
            AND (%(q)s::text IS NULL OR concat_ws(' ', p.name, p.variety, p.notes, g.name) ILIKE '%%' || %(q)s || '%%')
            ORDER BY s.sort NULLS LAST, s.space_id NULLS LAST, c.name NULLS LAST, p.started_on DESC""",
                            {"space": space_id, "q": (q or "").strip() or None}).fetchall()


@router.post("/garden/plantings", status_code=201)
def add_planting(body: PlantingIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
    with db() as conn:
        data = from_guide(conn, data)
        if not data.get("name"):
            raise HTTPException(422, "Give it a name, or pick it from the guide.")
        if data.get("stage") is None:
            data["stage"] = {"Seed": "Sown"}.get(data.get("source"), "Growing")
        planting_id = insert_row(conn, "garden_plantings", data, "planting_id")
        if data.get("item_id"):          # sown from a seed packet / planted from a seedling you had: one fewer
            conn.execute("UPDATE garden_items SET qty = GREATEST(qty - 1, 0) WHERE item_id = %s AND qty IS NOT NULL", (data["item_id"],))
        return fetch_planting(conn, planting_id)


@router.get("/garden/plantings/{planting_id}")
def get_planting(planting_id: int):
    with db() as conn:
        return fetch_planting(conn, planting_id)


@router.patch("/garden/plantings/{planting_id}")
def update_planting(planting_id: int, body: PlantingPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "source", "stage", "started_on", "quantity"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        current = fetch_planting(conn, planting_id)
        if data.get("stage") in ENDED and not current["ended_on"] and "ended_on" not in data:
            data["ended_on"] = conn.execute("SELECT current_date AS d").fetchone()["d"]
            data.setdefault("end_reason", "Died" if data["stage"] == "Died" else current["end_reason"] or "Harvested out")
        elif data.get("stage") and data["stage"] not in ENDED and current["stage"] in ENDED:
            data.update(ended_on=None, end_reason=None)       # brought back
        if "guide_id" in data and data["guide_id"] != current["guide_id"] and data["guide_id"]:
            data = from_guide(conn, {**data, "started_on": data.get("started_on", current["started_on"]), "source": current["source"]})
        if "container_id" in data and data["container_id"] != current["container_id"]:
            if data["container_id"] is not None:
                found(conn.execute("SELECT 1 FROM garden_containers WHERE container_id = %s", (data["container_id"],)).fetchone(), "Container")
            where = conn.execute("SELECT name FROM garden_containers WHERE container_id = %s", (data["container_id"],)).fetchone()
            insert_row(conn, "garden_logs", {"planting_id": planting_id, "kind": "Moved",
                                             "text": f"Moved to {where['name']}" if where else "Taken out of its pot"}, "log_id")
        update_row(conn, "garden_plantings", "planting_id", planting_id, data)
        return fetch_planting(conn, planting_id)


@router.delete("/garden/plantings/{planting_id}", status_code=204)
def delete_planting(planting_id: int):
    """Remove a plant and its history (to keep the history, set its stage to Done or Died instead)."""
    with db() as conn:
        found(conn.execute("DELETE FROM garden_plantings WHERE planting_id = %s RETURNING planting_id", (planting_id,)).fetchone(), "Plant")
    return Response(status_code=204)


class PropagateIn(BaseModel):
    container_id: int | None = None
    quantity: int = Field(1, ge=1, le=100)
    source: str = Field("Cutting", pattern="^(Cutting|Division|Seed)$")


@router.post("/garden/plantings/{planting_id}/propagate", status_code=201)
def propagate(planting_id: int, body: PropagateIn):
    """A new plant grown from this one (a cutting, a division, or its saved seed), linked back to it."""
    with db() as conn:
        parent = fetch_planting(conn, planting_id)
        data = from_guide(conn, {"name": parent["name"], "variety": parent["variety"], "guide_id": parent["guide_id"],
                                 "parent_id": planting_id, "container_id": body.container_id, "quantity": body.quantity,
                                 "source": body.source, "stage": "Sown" if body.source == "Seed" else "Seedling",
                                 "water_every_days": parent["water_every_days"], "feed_every_days": parent["feed_every_days"]})
        new_id = insert_row(conn, "garden_plantings", data, "planting_id")
        insert_row(conn, "garden_logs", {"planting_id": planting_id, "kind": "Note",
                                         "text": f"Took {body.quantity} {body.source.lower()}{'s' if body.quantity > 1 else ''} to grow on"}, "log_id")
        return fetch_planting(conn, new_id)


# ---------------------------------------------------------------------------------------------
# Care: watered / fed
# ---------------------------------------------------------------------------------------------
class CareIn(BaseModel):
    action: str = Field(pattern="^(watered|fed)$")
    planting_ids: list[int] | None = Field(None, max_length=500)
    container_id: int | None = None
    space_id: int | None = None
    all_due: bool = False                 # everything whose watering (or feeding) is due today
    text: str | None = Field(None, max_length=500)    # e.g. "liquid seaweed"


@router.post("/garden/care")
def care(body: CareIn):
    """Mark plants watered or fed today: some plants, a container's, a space's, or everything due. One log each."""
    col, kind, due = (("last_watered_on", "Watered", "water_due_on") if body.action == "watered"
                      else ("last_fed_on", "Fed", "feed_due_on"))
    with db() as conn:
        rows = conn.execute(PLANTING_SELECT + " WHERE p.stage NOT IN ('Planned', 'Done', 'Died')").fetchall()
        if body.all_due:
            d = today(conn)
            picked = [p for p in rows if p[due] and p[due] <= d]
        elif body.planting_ids is not None:
            picked = [p for p in rows if p["planting_id"] in set(body.planting_ids)]
        elif body.container_id is not None:
            picked = [p for p in rows if p["container_id"] == body.container_id]
        elif body.space_id is not None:
            picked = [p for p in rows if p["space_id"] == body.space_id]
        else:
            raise HTTPException(422, "Say which plants: planting_ids, a container, a space, or all_due.")
        for p in picked:
            conn.execute(f"UPDATE garden_plantings SET {col} = current_date WHERE planting_id = %s", (p["planting_id"],))
            insert_row(conn, "garden_logs", {"planting_id": p["planting_id"], "kind": kind, "text": (body.text or "").strip() or None},
                       "log_id")
        return {"done": len(picked), "names": [p["name"] for p in picked]}


def today(conn) -> date:
    return conn.execute("SELECT current_date AS d").fetchone()["d"]


# ---------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------------------
# Shared with garden_logs.py and garden_today.py: the log and task SELECTs
# ---------------------------------------------------------------------------------------------
LOG_SELECT = """
SELECT l.log_id, l.planting_id, l.container_id, l.space_id, l.kind, l.happened_on, l.text, l.amount::float8 AS amount, l.unit,
       l.tags, l.created_at,
       COALESCE((SELECT json_agg(json_build_object('photo_id', ph.photo_id, 'url', '/api/garden/photos/' || ph.photo_id)
                                 ORDER BY ph.photo_id) FROM garden_photos ph WHERE ph.log_id = l.log_id), '[]') AS photos
FROM garden_logs l"""

def logs_for(conn, column: str, value: int, limit: int = 200) -> list[dict]:
    return conn.execute(LOG_SELECT + f" WHERE l.{column} = %s ORDER BY l.happened_on DESC, l.log_id DESC LIMIT %s",
                        (value, limit)).fetchall()

TASK_SELECT = """
SELECT t.task_id, t.title, t.planting_id, t.container_id, t.space_id, t.due_on, t.repeat_days, t.notes, t.done_on,
       p.name AS planting_name, c.name AS container_name, s.name AS space_name, t.due_on <= current_date AS due
FROM garden_tasks t
LEFT JOIN garden_plantings p ON p.planting_id = t.planting_id
LEFT JOIN garden_containers c ON c.container_id = t.container_id
LEFT JOIN garden_spaces s ON s.space_id = t.space_id"""
