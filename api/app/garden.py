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
Plant guides and what to sow now: garden_guide.py. Supplies, seeds and Bunnings: garden_items.py.
"""
import re
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from . import openmeteo
from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes, photo_response, read_photo

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
# Logs and photos
# ---------------------------------------------------------------------------------------------
class LogFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(LOG_KINDS))
    happened_on: date | None = None
    text: str | None = Field(None, max_length=10000)
    amount: float | None = Field(None, ge=0, le=1000000)
    unit: str | None = Field(None, max_length=20)
    tags: list[str] | None = Field(None, max_length=20)


class LogIn(LogFields):
    planting_id: int | None = None
    container_id: int | None = None
    space_id: int | None = None


LOG_SELECT = """
SELECT l.log_id, l.planting_id, l.container_id, l.space_id, l.kind, l.happened_on, l.text, l.amount::float8 AS amount, l.unit,
       l.tags, l.created_at,
       COALESCE((SELECT json_agg(json_build_object('photo_id', ph.photo_id, 'url', '/api/garden/photos/' || ph.photo_id)
                                 ORDER BY ph.photo_id) FROM garden_photos ph WHERE ph.log_id = l.log_id), '[]') AS photos
FROM garden_logs l"""


def logs_for(conn, column: str, value: int, limit: int = 200) -> list[dict]:
    return conn.execute(LOG_SELECT + f" WHERE l.{column} = %s ORDER BY l.happened_on DESC, l.log_id DESC LIMIT %s",
                        (value, limit)).fetchall()


def after_log(conn, log: dict):
    """What a log means for its plant: watered / fed dates, stage changes, a repotting date."""
    p = log["planting_id"]
    if p:
        if log["kind"] == "Watered":
            conn.execute("UPDATE garden_plantings SET last_watered_on = GREATEST(COALESCE(last_watered_on, %(d)s), %(d)s) "
                         "WHERE planting_id = %(p)s", {"d": log["happened_on"], "p": p})
        elif log["kind"] == "Fed":
            conn.execute("UPDATE garden_plantings SET last_fed_on = GREATEST(COALESCE(last_fed_on, %(d)s), %(d)s) "
                         "WHERE planting_id = %(p)s", {"d": log["happened_on"], "p": p})
        moves = {"Sprouted": ("Sprouted", ("Planned", "Sown")),
                 "Flowered": ("Flowering", ("Planned", "Sown", "Sprouted", "Seedling", "Growing")),
                 "Harvested": ("Harvesting", ("Planned", "Sown", "Sprouted", "Seedling", "Growing", "Flowering", "Fruiting"))}
        if log["kind"] in moves:
            stage, before = moves[log["kind"]]
            conn.execute("UPDATE garden_plantings SET stage = %s WHERE planting_id = %s AND stage = ANY(%s)", (stage, p, list(before)))
    if log["kind"] == "Repotted" and log["container_id"]:
        conn.execute("UPDATE garden_containers SET potted_on = %s WHERE container_id = %s", (log["happened_on"], log["container_id"]))


def fetch_log(conn, log_id: int) -> dict:
    return found(conn.execute(LOG_SELECT + " WHERE l.log_id = %s", (log_id,)).fetchone(), "Note")


@router.post("/garden/logs", status_code=201)
def add_log(body: LogIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
    if not (data.get("planting_id") or data.get("container_id") or data.get("space_id")):
        raise HTTPException(422, "Say what it's about: a plant, a container or a space.")
    data["tags"] = [t.strip()[:40] for t in data.get("tags") or [] if t.strip()]
    with db() as conn:
        log_id = insert_row(conn, "garden_logs", data, "log_id")
        log = fetch_log(conn, log_id)
        after_log(conn, log)
        return log


@router.patch("/garden/logs/{log_id}")
def update_log(log_id: int, body: LogFields):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    for required in ("kind", "happened_on"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    if "tags" in data:
        data["tags"] = [t.strip()[:40] for t in data["tags"] or [] if t.strip()]
    with db() as conn:
        fetch_log(conn, log_id)
        update_row(conn, "garden_logs", "log_id", log_id, data)
        return fetch_log(conn, log_id)


@router.delete("/garden/logs/{log_id}", status_code=204)
def delete_log(log_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM garden_logs WHERE log_id = %s RETURNING log_id", (log_id,)).fetchone(), "Note")
    return Response(status_code=204)


@router.post("/garden/logs/{log_id}/photos", status_code=201)
async def add_photo(log_id: int, request: Request):
    """A photo (the body, shrunk by the browser) on a note. A photo never changes: a new one gets a new id."""
    image, image_type = await read_photo(request)
    with db() as conn:
        fetch_log(conn, log_id)
        photo_id = insert_row(conn, "garden_photos", {"log_id": log_id, "image": image, "image_type": image_type}, "photo_id")
        return {"photo_id": photo_id, "url": f"/api/garden/photos/{photo_id}"}


@router.get("/garden/photos/{photo_id}")
def get_photo(photo_id: int):
    with db() as conn:
        row = found(conn.execute("SELECT image, image_type FROM garden_photos WHERE photo_id = %s", (photo_id,)).fetchone(), "Photo")
    return photo_response(row["image"], row["image_type"])


@router.delete("/garden/photos/{photo_id}", status_code=204)
def delete_photo(photo_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM garden_photos WHERE photo_id = %s RETURNING photo_id", (photo_id,)).fetchone(), "Photo")
    return Response(status_code=204)


@router.get("/garden/photos")
def list_photos(planting_id: int | None = None, container_id: int | None = None, space_id: int | None = None,
                limit: int = Query(60, ge=1, le=500)):
    """Photos, newest first: of one plant, container or space - or all of them (the garden's gallery)."""
    with db() as conn:
        return conn.execute("""
            SELECT ph.photo_id, '/api/garden/photos/' || ph.photo_id AS url, l.log_id, l.kind, l.happened_on, l.text,
                   l.planting_id, l.container_id, l.space_id, p.name AS planting_name
            FROM garden_photos ph JOIN garden_logs l USING (log_id) LEFT JOIN garden_plantings p ON p.planting_id = l.planting_id
            WHERE (%(p)s::int IS NULL OR l.planting_id = %(p)s) AND (%(c)s::int IS NULL OR l.container_id = %(c)s)
              AND (%(s)s::int IS NULL OR l.space_id = %(s)s)
            ORDER BY l.happened_on DESC, ph.photo_id DESC LIMIT %(n)s""",
                            {"p": planting_id, "c": container_id, "s": space_id, "n": limit}).fetchall()


# ---------------------------------------------------------------------------------------------
# Tasks (your own reminders)
# ---------------------------------------------------------------------------------------------
class TaskFields(BaseModel):
    planting_id: int | None = None
    container_id: int | None = None
    space_id: int | None = None
    due_on: date | None = None
    repeat_days: int | None = Field(None, ge=1, le=365)
    notes: str | None = Field(None, max_length=2000)


class TaskIn(TaskFields):
    title: str = Field(min_length=1, max_length=200)


class TaskPatch(TaskFields):
    title: str | None = Field(None, min_length=1, max_length=200)


TASK_SELECT = """
SELECT t.task_id, t.title, t.planting_id, t.container_id, t.space_id, t.due_on, t.repeat_days, t.notes, t.done_on,
       p.name AS planting_name, c.name AS container_name, s.name AS space_name, t.due_on <= current_date AS due
FROM garden_tasks t
LEFT JOIN garden_plantings p ON p.planting_id = t.planting_id
LEFT JOIN garden_containers c ON c.container_id = t.container_id
LEFT JOIN garden_spaces s ON s.space_id = t.space_id"""


@router.get("/garden/tasks")
def list_tasks(include_done: bool = False):
    with db() as conn:
        return conn.execute(TASK_SELECT + (" " if include_done else " WHERE t.done_on IS NULL ")
                            + "ORDER BY t.done_on IS NOT NULL, t.due_on, lower(t.title)").fetchall()


@router.post("/garden/tasks", status_code=201)
def add_task(body: TaskIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("title",))
    with db() as conn:
        task_id = insert_row(conn, "garden_tasks", data, "task_id")
        return conn.execute(TASK_SELECT + " WHERE t.task_id = %s", (task_id,)).fetchone()


@router.patch("/garden/tasks/{task_id}")
def update_task(task_id: int, body: TaskPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    if "due_on" in data and data["due_on"] is None:
        raise HTTPException(422, "Due on can't be empty.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM garden_tasks WHERE task_id = %s", (task_id,)).fetchone(), "Reminder")
        update_row(conn, "garden_tasks", "task_id", task_id, data)
        return conn.execute(TASK_SELECT + " WHERE t.task_id = %s", (task_id,)).fetchone()


@router.post("/garden/tasks/{task_id}/done")
def task_done(task_id: int):
    """Done: a repeating reminder moves on to its next date (from today); a one-off is ticked off."""
    with db() as conn:
        t = found(conn.execute("SELECT * FROM garden_tasks WHERE task_id = %s", (task_id,)).fetchone(), "Reminder")
        if t["repeat_days"]:
            conn.execute("UPDATE garden_tasks SET due_on = current_date + repeat_days WHERE task_id = %s", (task_id,))
        else:
            conn.execute("UPDATE garden_tasks SET done_on = current_date WHERE task_id = %s", (task_id,))
        about = t["planting_id"] or t["container_id"] or t["space_id"]
        if about:
            insert_row(conn, "garden_logs", {"planting_id": t["planting_id"], "container_id": t["container_id"],
                                             "space_id": t["space_id"], "kind": "Note", "text": f"Done: {t['title']}"}, "log_id")
        return conn.execute(TASK_SELECT + " WHERE t.task_id = %s", (task_id,)).fetchone()


@router.delete("/garden/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM garden_tasks WHERE task_id = %s RETURNING task_id", (task_id,)).fetchone(), "Reminder")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Today, weather tips, summary, timeline, harvests
# ---------------------------------------------------------------------------------------------
def weather_tips(days: list[dict], spaces: list[dict]) -> list[dict]:
    """Plain advice for pots on a balcony from the next two days' forecast."""
    tips = []
    open_air = [s["name"] for s in spaces if not s["covered"] and s["kind"] not in ("Indoor", "Shelf", "Grow tent", "Windowsill")]
    outdoor = any(s["kind"] not in ("Indoor", "Shelf", "Grow tent", "Windowsill") for s in spaces) or not spaces
    for d, when in zip(days[:2], ("Today", "Tomorrow")):
        hot, gusts, rain, low, uv = d.get("max"), d.get("gusts"), d.get("rain_mm"), d.get("min"), d.get("uv")
        if hot is not None and hot >= 35:
            tips.append({"day": when, "kind": "heat", "text": f"Very hot ({hot:.0f}°): water pots early in the morning and again in the "
                         "evening; move seedlings and lettuce into shade."})
        elif hot is not None and hot >= 30:
            tips.append({"day": when, "kind": "heat", "text": f"Hot ({hot:.0f}°): check pots morning and evening - small pots and "
                         "hanging baskets dry out first."})
        if outdoor and gusts is not None and gusts >= 60:
            tips.append({"day": when, "kind": "wind", "text": f"Strong gusts up to {gusts:.0f} km/h: move light pots and tall plants "
                         "against the wall or inside, and take down hanging baskets."})
        elif outdoor and gusts is not None and gusts >= 45:
            tips.append({"day": when, "kind": "wind", "text": f"Windy (gusts {gusts:.0f} km/h): pots dry out faster; stake tall plants."})
        if open_air and rain is not None and rain >= 5:
            tips.append({"day": when, "kind": "rain", "text": f"Rain ({rain:.0f} mm): {', '.join(open_air)} may not need watering."})
        if low is not None and low <= 5:
            tips.append({"day": when, "kind": "cold", "text": f"Cold night ({low:.0f}°): bring basil, chillies and other tender "
                         "plants inside or against the wall."})
        if outdoor and uv is not None and uv >= 11:
            tips.append({"day": when, "kind": "uv", "text": "Extreme UV: shade seedlings from the midday sun."})
    return tips


def weather(conn) -> dict | None:
    s = garden_settings(conn)
    if s["lat"] is None:
        return None
    spaces = conn.execute("SELECT name, kind, covered FROM garden_spaces").fetchall()
    try:
        days = openmeteo.forecast(s["lat"], s["lon"])
    except openmeteo.WeatherError as e:
        return {"place": s["place_name"], "error": str(e), "days": [], "tips": []}
    return {"place": s["place_name"], "error": None, "days": days, "tips": weather_tips(days, spaces)}


@router.get("/garden/today")
def garden_today():
    """What needs doing: watering and feeding due (oldest first), ready to harvest, your reminders, weather tips."""
    with db() as conn:
        current = conn.execute(PLANTING_SELECT + " WHERE p.stage NOT IN ('Planned', 'Done', 'Died') ORDER BY s.sort NULLS LAST, c.name, p.name").fetchall()
        d = today(conn)
        tasks = conn.execute(TASK_SELECT + " WHERE t.done_on IS NULL AND t.due_on <= current_date + 2 ORDER BY t.due_on").fetchall()
        planned = conn.execute(PLANTING_SELECT + " WHERE p.stage = 'Planned' ORDER BY p.started_on").fetchall()
        return {
            "today": d,
            "water": sorted([p for p in current if p["water_due_on"] and p["water_due_on"] <= d], key=lambda p: p["water_due_on"]),
            "feed": sorted([p for p in current if p["feed_due_on"] and p["feed_due_on"] <= d], key=lambda p: p["feed_due_on"]),
            "harvest": [p for p in current if p["harvest_ready"]],
            "tasks": tasks, "planned": planned,
            "weather": weather(conn),
            "growing": len(current),
        }


@router.get("/garden/summary")
def garden_summary():
    """For Home: plants growing, how many need water, ready to pick, reminders due, harvests this year."""
    with db() as conn:
        current = conn.execute(PLANTING_SELECT + " WHERE p.stage NOT IN ('Planned', 'Done', 'Died')").fetchall()
        d = today(conn)
        return {
            "growing": len(current),
            "need_water": sum(1 for p in current if p["water_due_on"] and p["water_due_on"] <= d),
            "need_feed": sum(1 for p in current if p["feed_due_on"] and p["feed_due_on"] <= d),
            "ready": sum(1 for p in current if p["harvest_ready"]),
            "tasks_due": conn.execute("SELECT count(*) AS n FROM garden_tasks WHERE done_on IS NULL AND due_on <= current_date").fetchone()["n"],
            "harvests_this_year": conn.execute("SELECT count(*) AS n FROM garden_logs WHERE kind = 'Harvested' "
                                               "AND happened_on >= date_trunc('year', current_date)").fetchone()["n"],
            "spaces": conn.execute("SELECT count(*) AS n FROM garden_spaces").fetchone()["n"],
        }


@router.get("/garden/harvests")
def harvests(year: int | None = Query(None, ge=1900, le=2200)):
    """Every harvest (newest first), with totals per plant and per month, by unit."""
    with db() as conn:
        y = year or today(conn).year
        rows = conn.execute(LOG_SELECT.replace("FROM garden_logs l", ", p.name AS planting_name, p.variety FROM garden_logs l "
                                               "JOIN garden_plantings p ON p.planting_id = l.planting_id")
                            + " WHERE l.kind = 'Harvested' AND extract(year FROM l.happened_on) = %s "
                            "ORDER BY l.happened_on DESC, l.log_id DESC", (y,)).fetchall()
    by_plant: dict = {}
    by_month: dict = {}
    for r in rows:
        unit = r["unit"] or "times"
        amount = r["amount"] if r["amount"] is not None else 1
        key = (r["planting_name"], unit)
        by_plant[key] = by_plant.get(key, 0) + amount
        mkey = (r["happened_on"].strftime("%Y-%m"), unit)
        by_month[mkey] = by_month.get(mkey, 0) + amount
    years = list(range(y - 3, y + 1))
    return {"year": y, "years": years, "harvests": rows,
            "by_plant": sorted([{"name": n, "unit": u, "amount": round(a, 2)} for (n, u), a in by_plant.items()],
                               key=lambda x: (-x["amount"], x["name"])),
            "by_month": [{"month": m, "unit": u, "amount": round(a, 2)} for (m, u), a in sorted(by_month.items())]}
