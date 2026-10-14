"""Models (kits): your stash, and the paints each one needs.

Status runs Wanted -> In stash -> In progress / On hold -> Finished (or Gone: sold, given away).
"Shelf of shame" = kits you own but haven't finished (In stash, In progress, On hold).
Each model belongs to a hobby (Scale model / Warhammer / Gundam), which has its own build steps
(`stage` = the last one done). Warhammer boxes count minis (figures, figures_done); Gundam kits
have a grade (HG, MG...).

A model's paint list is a checklist. Each paint is matched to your inventory by brand + product
code, so it shows as "have it" automatically while you own one; a line can also be a mix (have
it when you own every part); anything else can be ticked by hand (have_it). Time tracking and
the build log are in build.py.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import colours, paints, tamiya
from .db import (HOBBIES, MODEL_STATUSES, STAGES, brand_id as brand_named, db, ensure_brand, found,
                 insert_row, update_row)
from .products import tamiya_product
from .settings import price_for

router = APIRouter(prefix="/api", tags=["models"])

Status = Literal[tuple(MODEL_STATUSES)]
Hobby = Literal[tuple(HOBBIES)]
UNBUILT = ("In stash", "In progress", "On hold")  # the shelf of shame
NOT_STARTED = ("Wanted", "In stash", "On hold")   # ticking off a build step moves these to In progress


def scalemates_url():
    """A Scalemates kit page, opened in the user's browser (never fetched by the app)."""
    return Field(None, pattern=r"^https?://(www\.)?scalemates\.com/\S+$")


class ModelIn(BaseModel):
    name: str = Field(min_length=1)
    brand_id: int | None = None
    product_code: str | None = None
    scale: str | None = None
    status: Status = "In stash"
    notes: str | None = None
    scalemates_url: str | None = scalemates_url()
    price_paid: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    purchased_from: str | None = None
    hobby: Hobby = "Scale model"
    stage: str | None = None
    skipped_steps: list[str] | None = None
    grade: str | None = None
    faction: str | None = None
    figures: int = Field(1, ge=1)
    figures_done: int = Field(0, ge=0)
    brand_name: str | None = Field(None, min_length=1)  # a brand you haven't used yet (instead of brand_id)


class ModelPatch(BaseModel):
    name: str | None = Field(None, min_length=1)
    brand_id: int | None = None
    product_code: str | None = None
    scale: str | None = None
    status: Status | None = None
    notes: str | None = None
    scalemates_url: str | None = scalemates_url()
    price_paid: Decimal | None = Field(None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    purchased_from: str | None = None
    started_on: date | None = None
    finished_on: date | None = None
    hobby: Hobby | None = None
    stage: str | None = None
    skipped_steps: list[str] | None = None
    grade: str | None = None
    faction: str | None = None
    figures: int | None = Field(None, ge=1)
    figures_done: int | None = Field(None, ge=0)
    brand_name: str | None = Field(None, min_length=1)


class PaintsIn(BaseModel):
    """One paint per line: "XF-76 Grey Green (IJN) <tab> The whole exterior", or a mix:
    "XF-62 + XF-2 (3:1) - Exterior". `purpose` is used for a single line typed without a tab."""
    text: str = Field(min_length=1)
    purpose: str | None = None


class PaintPatch(BaseModel):
    paint_name: str | None = Field(None, min_length=1)
    purpose: str | None = None
    have_it: bool | None = None
    sort_order: int | None = None


class KitPaint(BaseModel):
    product_code: str = Field(min_length=1)
    paint_name: str = Field(min_length=1)


class KitPaintsIn(BaseModel):
    paints: list[KitPaint]


OWNED = ("EXISTS (SELECT 1 FROM supplies s WHERE s.brand_id = mp.brand_id "
         "AND s.product_code = mp.product_code AND s.qty_on_hand > 0)")
HAVE = f"(mp.have_it OR {OWNED} OR (mp.mix_id IS NOT NULL AND {colours.MIX_COMPLETE.format(col='mp.mix_id')}))"

MODEL_SELECT = f"""
SELECT m.*, b.name AS brand,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.fetched_at AS photo_updated, p.source_url,
       (SELECT count(*) FROM model_paints mp WHERE mp.model_id = m.model_id) AS paints_total,
       (SELECT count(*) FROM model_paints mp WHERE mp.model_id = m.model_id AND {HAVE}) AS paints_have,
       (SELECT COALESCE(round(sum(extract(epoch FROM (COALESCE(x.ended_at, now()) - x.started_at))) / 60), 0)
          FROM model_sessions x WHERE x.model_id = m.model_id)::int AS total_minutes,
       (SELECT x.started_at FROM model_sessions x WHERE x.model_id = m.model_id AND x.ended_at IS NULL) AS running_since,
       (SELECT count(*) FROM model_log l WHERE l.model_id = m.model_id) AS log_count
FROM models m
LEFT JOIN brands b ON b.brand_id = m.brand_id
LEFT JOIN product_info p ON p.brand_id = m.brand_id AND p.product_code = m.product_code
"""

# Each paint with what your inventory says about it.
PAINTS_SELECT = f"""
SELECT mp.*, b.name AS brand, x.name AS mix_name,
       owned.supply_id, COALESCE(owned.qty_on_hand, 0) AS owned_qty, owned.condition, owned.stock_status,
       (COALESCE(owned.qty_on_hand, 0) > 0) AS in_inventory,
       {HAVE} AS have,
       EXISTS (SELECT 1 FROM wishlist w WHERE w.brand_id = mp.brand_id
               AND w.product_code = mp.product_code) AS on_wishlist,
       p.product_info_id, (p.image IS NOT NULL) AS has_image, p.fetched_at AS photo_updated,
       cp.thumb_url AS catalog_thumb
FROM model_paints mp
LEFT JOIN brands b ON b.brand_id = mp.brand_id
LEFT JOIN mixes x ON x.mix_id = mp.mix_id
LEFT JOIN LATERAL (
    SELECT v.supply_id, v.qty_on_hand, v.condition, v.stock_status
    FROM supplies s JOIN v_supplies v USING (supply_id)
    WHERE s.brand_id = mp.brand_id AND s.product_code = mp.product_code
    LIMIT 1
) owned ON true
LEFT JOIN product_info p ON p.brand_id = mp.brand_id AND p.product_code = mp.product_code
LEFT JOIN catalog_products cp ON cp.brand_id = mp.brand_id AND cp.product_code = mp.product_code
WHERE mp.model_id = %s
ORDER BY mp.sort_order, mp.model_paint_id
"""


def fetch_model(conn, model_id):
    model = found(conn.execute(MODEL_SELECT + " WHERE m.model_id = %s", (model_id,)).fetchone(),
                  f"Model {model_id}")
    rows = conn.execute(PAINTS_SELECT, (model_id,)).fetchall()
    # Paints you don't have, but own something matching (same code / same name / your match).
    alternatives = colours.owned_alternatives(conn, [
        {"key": r["model_paint_id"], **r} for r in rows if not r["have"] and r["mix_id"] is None])
    mixes = {r["mix_id"]: colours.fetch_mix(conn, r["mix_id"]) for r in rows if r["mix_id"]}
    paints_ = [{**r, "alternative": alternatives.get(r["model_paint_id"]),
                "mix": mixes.get(r["mix_id"])} for r in rows]
    sessions = conn.execute(
        "SELECT session_id, started_at, ended_at, note, "
        "round(extract(epoch FROM (COALESCE(ended_at, now()) - started_at)) / 60)::int AS minutes "
        "FROM model_sessions WHERE model_id = %s ORDER BY started_at DESC LIMIT 50", (model_id,)).fetchall()
    log = conn.execute(
        "SELECT entry_id, entry_date, text, (photo IS NOT NULL) AS has_photo, created_at, photo_updated "
        "FROM model_log WHERE model_id = %s ORDER BY entry_date DESC, entry_id DESC", (model_id,)).fetchall()
    return {**model, "paints": paints_, "sessions": sessions, "log": log}


def tamiya_id_of(conn):
    return brand_named(conn, "Tamiya")


def date_status(conn, model_id, status):
    """Starting a kit dates it; finishing it dates that too (unless you've set the dates yourself)."""
    if status in ("In progress", "Finished"):
        conn.execute("UPDATE models SET started_on = COALESCE(started_on, current_date) WHERE model_id = %s",
                     (model_id,))
    if status == "Finished":
        conn.execute("UPDATE models SET finished_on = COALESCE(finished_on, current_date) WHERE model_id = %s",
                     (model_id,))


def build_steps(current: dict, data: dict, steps: list[str]):
    """How the stage, the skipped steps and Finished go together (changes `data`):
    - Complete is the last step: reaching it finishes the kit; a kit marked Finished is put at
      Complete; un-finishing a kit at Complete takes it back to its last step really done
    - moving the stage ahead skips the steps in between (not the first, Built: snap-fit kits go
      Built -> Complete); moving it back forgets skips after it
    - skipped_steps sent on their own mark steps before the stage skipped / done again"""
    last = steps[-1]
    old_stage, old_skipped = current.get("stage"), list(current.get("skipped_steps") or [])
    status = data.get("status")
    if "stage" not in data and old_stage:
        if status == "Finished" and old_stage != last:
            data["stage"] = last
        elif status and status != "Finished" and old_stage == last:
            data["stage"] = next((s for s in reversed(steps[:-1]) if s not in old_skipped), None)
    elif not data.get("stage") and not old_stage and status == "Finished":
        data["stage"] = last
    if data.get("stage") == last and "status" not in data and current.get("status") != "Finished":
        data["status"] = "Finished"
    elif "stage" in data and data["stage"] != last and "status" not in data and current.get("status") == "Finished":
        data["status"] = "In progress"
    stage = data["stage"] if "stage" in data else old_stage
    at = steps.index(stage) if stage in steps else -1
    if "skipped_steps" in data and data["skipped_steps"] is not None:
        wanted = data["skipped_steps"]
        bad = [s for s in wanted if s not in steps[1:at]]
        if bad:
            raise HTTPException(422, f"Only steps between {steps[0]} and the step you're on can be skipped "
                                     f"(not {', '.join(bad)}).")
        data["skipped_steps"] = [s for s in steps if s in wanted]
    elif "stage" in data:
        was = steps.index(old_stage) if old_stage in steps else -1
        if at > was:
            data["skipped_steps"] = [s for s in steps if s in old_skipped or s in steps[max(was + 1, 1):at]]
        else:
            data["skipped_steps"] = [s for s in old_skipped if s in steps and steps.index(s) < at]
    else:
        data.pop("skipped_steps", None)


def tidy_model(conn, current: dict, data: dict) -> dict:
    """The rules for a new or changed model, applied to `data` (the fields being set):
    - brand_name: a brand you haven't used yet is added to your brands
    - the stage must be one of the hobby's steps; changing hobby drops a stage it doesn't have
    - ticking off a step on a kit you haven't started moves it to In progress
    - steps (see build_steps): jumping ahead skips the steps between; Complete = Finished
    - fewer minis in the box than you'd marked done lowers the done count to match"""
    name = data.pop("brand_name", None)
    if name and data.get("brand_id") is None:
        data["brand_id"] = ensure_brand(conn, name.strip())
    hobby = data.get("hobby") or current.get("hobby") or "Scale model"
    stage = data["stage"] if "stage" in data else current.get("stage")
    if stage is not None and stage not in STAGES[hobby]:
        if "stage" in data:
            raise HTTPException(422, f"'{stage}' isn't a {hobby} build step. Steps: {', '.join(STAGES[hobby])}.")
        data["stage"] = None                        # the hobby changed: start its steps afresh
    build_steps(current, data, STAGES[hobby])
    if data.get("stage") and "status" not in data and current.get("status", "In stash") in NOT_STARTED:
        data["status"] = "In progress"
    figures = data.get("figures") or current.get("figures") or 1
    done = data["figures_done"] if "figures_done" in data else current.get("figures_done", 0)
    if done is not None and done > figures:
        if "figures_done" in data and "figures" not in data:
            raise HTTPException(422, f"There are only {figures} minis in the box.")
        data["figures_done"] = figures
    return data


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@router.get("/models")
def list_models():
    with db() as conn:
        return conn.execute(MODEL_SELECT + """
            ORDER BY CASE m.status WHEN 'In progress' THEN 0 WHEN 'In stash' THEN 1 WHEN 'On hold' THEN 2
                                   WHEN 'Wanted' THEN 3 WHEN 'Finished' THEN 4 ELSE 5 END,
                     m.created_at DESC""").fetchall()


# Declared before /models/{model_id} so "summary" isn't mistaken for an id.
@router.get("/models/summary")
def stash_summary():
    """The shelf of shame: how many kits you own but haven't finished, and what they cost;
    plus counts per status and hours spent."""
    with db() as conn:
        counts = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, count(*) AS n FROM models GROUP BY status").fetchall()}
        shame = conn.execute("SELECT count(*) AS kits, COALESCE(sum(price_paid), 0) AS value, "
                             "count(*) FILTER (WHERE price_paid IS NULL) AS unpriced "
                             "FROM models WHERE status = ANY(%s)", (list(UNBUILT),)).fetchone()
        minutes = conn.execute("SELECT COALESCE(round(sum(extract(epoch FROM (COALESCE(ended_at, now()) - started_at)))"
                               " / 60), 0)::int AS m FROM model_sessions").fetchone()["m"]
        return {"counts": {s: counts.get(s, 0) for s in MODEL_STATUSES}, "shelf_of_shame": shame,
                "total_minutes": minutes}


@router.post("/models", status_code=201)
def add_model(body: ModelIn):
    with db() as conn:
        data = tidy_model(conn, {}, body.model_dump())
        model_id = insert_row(conn, "models", data, "model_id")
        date_status(conn, model_id, data["status"])
        return fetch_model(conn, model_id)


@router.get("/models/{model_id}")
def get_model(model_id: int):
    with db() as conn:
        return fetch_model(conn, model_id)


@router.patch("/models/{model_id}")
def update_model(model_id: int, body: ModelPatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        data = tidy_model(conn, fetch_model(conn, model_id), data)
        update_row(conn, "models", "model_id", model_id, data)
        date_status(conn, model_id, data.get("status"))
        return fetch_model(conn, model_id)


@router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM models WHERE model_id = %s RETURNING model_id", (model_id,)).fetchone(),
              f"Model {model_id}")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# A model's paints
# ---------------------------------------------------------------------------
def next_order(conn, model_id) -> int:
    return conn.execute("SELECT COALESCE(max(sort_order), 0) AS n FROM model_paints WHERE model_id = %s",
                        (model_id,)).fetchone()["n"]


@router.post("/models/{model_id}/paints", status_code=201)
def add_paints(model_id: int, body: PaintsIn):
    """Add one paint, or paste a whole list (one per line). Codes like XF-76 or ones you own
    are linked to your inventory; "XF-62 + XF-2 (3:1)" becomes a mix; anything else is kept as
    a name you tick by hand."""
    lines = [ln for ln in body.text.splitlines() if ln.strip()]
    with db() as conn:
        fetch_model(conn, model_id)  # 404 if the model doesn't exist
        tamiya_id = tamiya_id_of(conn)
        order = next_order(conn, model_id)
        for line in lines:
            paint, purpose = paints.parse_line(line)
            if not paint:
                continue
            if purpose is None and len(lines) == 1:
                purpose = (body.purpose or "").strip() or None
            if paints.is_mix(paint):
                mix_id = colours.create_mix(conn, paint)
                row = {"brand_id": None, "product_code": None, "paint_name": paint, "mix_id": mix_id}
            else:
                row = {**paints.to_product(conn, paint, tamiya_id), "mix_id": None}
            order += 1
            insert_row(conn, "model_paints", {**row, "model_id": model_id, "purpose": purpose,
                                              "sort_order": order}, "model_paint_id")
        return fetch_model(conn, model_id)


def paint_owner(conn, paint_id) -> int:
    return found(conn.execute("SELECT model_id FROM model_paints WHERE model_paint_id = %s",
                              (paint_id,)).fetchone(), "Paint")["model_id"]


@router.patch("/model-paints/{paint_id}")
def update_paint(paint_id: int, body: PaintPatch):
    with db() as conn:
        model_id = paint_owner(conn, paint_id)
        update_row(conn, "model_paints", "model_paint_id", paint_id, body.model_dump(exclude_unset=True))
        return fetch_model(conn, model_id)


@router.delete("/model-paints/{paint_id}")
def delete_paint(paint_id: int):
    with db() as conn:
        model_id = paint_owner(conn, paint_id)
        conn.execute("DELETE FROM model_paints WHERE model_paint_id = %s", (paint_id,))
        return fetch_model(conn, model_id)


@router.post("/models/{model_id}/wishlist")
def wish_for_missing_paints(model_id: int):
    """Put every paint this model still needs on the wishlist (parts of mixes too). Paints
    without a brand + code can't be matched to a product, so they're reported rather than added."""
    with db() as conn:
        model = fetch_model(conn, model_id)
        paint_category = conn.execute("SELECT category_id FROM categories WHERE name = 'Paint'").fetchone()
        wanted = []
        for p in model["paints"]:
            if p["have"]:
                continue
            if p["mix"]:
                wanted += [{**part, "purpose": f"{p['purpose'] or 'mix'} ({p['paint_name']})"}
                           for part in p["mix"]["parts"] if part["owned_qty"] <= 0]
            else:
                wanted.append(p)
        added, skipped, seen = [], [], set()
        for p in wanted:
            if p["brand_id"] is None or not p["product_code"]:
                skipped.append(p["paint_name"])
                continue
            if (p["brand_id"], p["product_code"]) in seen:
                continue
            seen.add((p["brand_id"], p["product_code"]))
            info = conn.execute("""
                SELECT COALESCE(p.title, c.title) AS title, COALESCE(p.series, c.genre) AS series, p.description
                FROM (SELECT %(b)s::int AS b, %(c)s::text AS c) x
                LEFT JOIN product_info p ON p.brand_id = x.b AND p.product_code = x.c
                LEFT JOIN catalog_products c ON c.brand_id = x.b AND c.product_code = x.c""",
                {"b": p["brand_id"], "c": p["product_code"]}).fetchone()
            guess = tamiya.suggest(info["title"], info["series"], info["description"], p["product_code"]) \
                if info["title"] else {}
            note = f"For {model['name']}: {p['purpose']}" if p.get("purpose") else f"For {model['name']}"
            row = conn.execute("""
                INSERT INTO wishlist (brand_id, product_code, name, category_id, paint_type, finish,
                                      size, est_price, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (brand_id, product_code) DO NOTHING RETURNING wish_id""",
                (p["brand_id"], p["product_code"], p["paint_name"], paint_category["category_id"],
                 guess.get("paint_type"), guess.get("finish"), guess.get("size"),
                 price_for(conn, info["title"], guess) if guess else None, note)).fetchone()
            if row:
                added.append(p["paint_name"])
        return {"added": added, "skipped": skipped, "model": fetch_model(conn, model_id)}


# ---------------------------------------------------------------------------
# Paints from a Tamiya kit's page ("Tamiya Colors required")
# ---------------------------------------------------------------------------
def kit_paint_entry(conn, paint: dict, on_model: set) -> dict:
    """One paint from the kit page, as the product you'd actually buy. Tamiya lists X/XF colours
    generically ("TAMIYA COLOR XF-62 OLIVE DRAB", item 0XF62); those become the Acrylic Mini,
    the range you use (T81762)."""
    colour = tamiya.colour_of(paint["title"])
    code = tamiya.paint_code(colour[0]) if colour else None   # X / XF only
    if code and not paint["item"].isdigit():                    # a generic colour page
        product_code = "T" + tamiya.item_number(code)
        suggested = True
    else:
        product_code = tamiya.product_code(paint["item"])
        suggested = False
    tamiya_id = tamiya_id_of(conn)
    owned = conn.execute("SELECT supply_id, qty_on_hand FROM supplies WHERE brand_id = %s AND product_code = %s",
                         (tamiya_id, product_code)).fetchone()
    return {"group": paint["group"], "item": paint["item"], "title": paint["title"],
            "product_code": product_code,
            "paint_name": paints.default_name(conn, tamiya_id, product_code, tamiya.your_style_name(paint["title"])),
            "suggested": suggested, "on_model": product_code in on_model,
            "owned_qty": owned["qty_on_hand"] if owned else 0}


def group_label(group: str, entries: list[dict]) -> str:
    """Tamiya repeats "Tamiya Colors for brush and airbrush painting" for each range: say which."""
    codes = {(tamiya.colour_of(e["title"]) or ("",))[0].split("-")[0] for e in entries}
    if codes == {"LP"}:
        return "Lacquer paints (LP)"
    if codes and codes <= {"X", "XF"}:
        return "Acrylic paints (X / XF) - as Acrylic Minis"
    if codes and codes <= {"TS", "AS", "PS"}:
        return "Spray cans"
    return group


@router.get("/models/{model_id}/kit-paints")
async def kit_paints(model_id: int, refresh: bool = False):
    """The paints Tamiya lists for this kit, grouped as on their page, each as the product you'd
    buy. `suggested` = the main X/XF colours (pre-ticked); the rest (lacquers, sprays,
    weathering, tools) are there if you want them. Read once from the kit page, then cached."""
    with db() as conn:
        model = fetch_model(conn, model_id)
        tamiya_id = tamiya_id_of(conn)
        if model["brand_id"] != tamiya_id or not model["product_code"]:
            raise HTTPException(422, "Only Tamiya kits list their paints: set the brand to Tamiya and the kit code.")
        cached = conn.execute("SELECT kit_paints FROM product_info WHERE brand_id = %s AND product_code = %s",
                              (tamiya_id, model["product_code"])).fetchone()
    if refresh or cached is None or cached["kit_paints"] is None:
        await tamiya_product(tamiya.item_number(model["product_code"]), refresh=True)
    with db() as conn:
        listed = conn.execute("SELECT title, kit_paints FROM product_info WHERE brand_id = %s AND product_code = %s",
                              (tamiya_id, model["product_code"])).fetchone()
        on_model = {p["product_code"] for p in model["paints"] if p["product_code"]}
        groups = []
        for paint in listed["kit_paints"] or []:
            if not groups or groups[-1]["section"] != paint.get("section"):
                groups.append({"section": paint.get("section"), "heading": paint["group"], "paints": []})
            groups[-1]["paints"].append(kit_paint_entry(conn, paint, on_model))
        for g in groups:
            g["label"] = group_label(g["heading"], g["paints"])
        return {"kit": listed["title"], "groups": groups}


@router.post("/models/{model_id}/kit-paints", status_code=201)
def add_kit_paints(model_id: int, body: KitPaintsIn):
    """Add the paints you picked from the kit's list (ones already on the checklist are skipped)."""
    with db() as conn:
        model = fetch_model(conn, model_id)
        tamiya_id = tamiya_id_of(conn)
        have = {p["product_code"] for p in model["paints"] if p["product_code"]}
        order = next_order(conn, model_id)
        for p in body.paints:
            if p.product_code in have:
                continue
            have.add(p.product_code)
            order += 1
            insert_row(conn, "model_paints", {"model_id": model_id, "brand_id": tamiya_id,
                                              "product_code": p.product_code, "paint_name": p.paint_name,
                                              "sort_order": order}, "model_paint_id")
        return fetch_model(conn, model_id)
