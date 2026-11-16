"""Paint recipes, and "can I paint this now?".

A recipe is a named list of steps ("base: Mephiston Red", "wash: Agrax Earthshade"). Each step has a paint - picked from
your supplies, or typed (a code like XF-76 is matched; so is a name you own) - and a note. A recipe can sit on a model
(and one of its units / minis) or on its own, and copy_recipe reuses it on another model.

"Can I paint this now?" looks at a recipe's paints, or a model's paint list, against your supplies:
  owned    you have it            low / out   you own it but it's running low / is empty
  missing  a paint with a code you don't own at all     free   typed text with no brand + code (can't be checked)
One tap puts the low, out and missing ones on the wishlist.
"""
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import paints
from .db import db, found, insert_row, tidy_text, update_row
from .models import fetch_model, tamiya_id_of
from .wishlist import wish_from_supplies

router = APIRouter(prefix="/api", tags=["recipes"])


class StepIn(BaseModel):
    label: str | None = Field(None, max_length=40)        # base, layer, wash, highlight...
    paint_text: str = Field("", max_length=200)           # typed paint (or the supply's name)
    supply_id: int | None = None                          # picked from your supplies
    note: str | None = Field(None, max_length=1000)


class RecipeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str | None = None
    model_id: int | None = None
    unit: str | None = Field(None, max_length=120)
    steps: list[StepIn] = []


class RecipePatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    notes: str | None = None
    model_id: int | None = None
    unit: str | None = Field(None, max_length=120)
    steps: list[StepIn] | None = None                     # sent = replaces all the steps


class CopyIn(BaseModel):
    model_id: int | None = None                           # None = a copy kept on its own
    name: str | None = Field(None, min_length=1, max_length=120)


# ---------------------------------------------------------------------------
# What your supplies say about a paint
# ---------------------------------------------------------------------------
def paint_state(conn, brand_id, product_code) -> dict:
    """{state, supply_id, qty, swatch} for one product: owned, low, out, missing, or free (no brand + code)."""
    if brand_id is None or not product_code:
        return {"state": "free", "supply_id": None, "qty": None, "swatch": None}
    row = conn.execute("SELECT s.supply_id, s.qty_on_hand, s.swatch, v.stock_status FROM supplies s "
                       "JOIN v_supplies v USING (supply_id) WHERE s.brand_id = %s AND s.product_code = %s",
                       (brand_id, product_code)).fetchone()
    if row is None:
        return {"state": "missing", "supply_id": None, "qty": 0, "swatch": None}
    state = "out" if row["qty_on_hand"] <= 0 else "low" if row["stock_status"] != "OK" else "owned"
    return {"state": state, "supply_id": row["supply_id"], "qty": row["qty_on_hand"], "swatch": row["swatch"]}


def summarise(items: list[dict]) -> dict:
    """Counts of each state; ready = nothing missing or out (low is still enough to paint with)."""
    counts = {k: sum(1 for i in items if i["state"] == k) for k in ("owned", "low", "out", "missing", "free")}
    return {**counts, "total": len(items), "to_buy": counts["low"] + counts["out"] + counts["missing"],
            "ready": counts["out"] + counts["missing"] == 0}


def to_wishlist(conn, items: list[dict], note: str) -> dict:
    """Low / out paints (ones you own) and missing paints (a code you don't own) onto the wishlist, skipping what's there."""
    category = conn.execute("SELECT category_id FROM categories WHERE name = 'Paint'").fetchone()
    supply_ids = sorted({i["supply_id"] for i in items if i["state"] in ("low", "out") and i["supply_id"]})
    added = [r["name"] for r in wish_from_supplies(conn, "s.supply_id = ANY(%s)", (supply_ids,), notes=note)] \
        if supply_ids else []
    seen = set()
    for i in items:
        key = (i.get("brand_id"), i.get("product_code"))
        if i["state"] != "missing" or key in seen or not category:
            continue
        seen.add(key)
        row = conn.execute("""INSERT INTO wishlist (brand_id, product_code, name, category_id, notes)
                              VALUES (%s, %s, %s, %s, %s) ON CONFLICT (brand_id, product_code) DO NOTHING
                              RETURNING wish_id""", (*key, i["name"], category["category_id"], note)).fetchone()
        if row:
            added.append(i["name"])
    return {"added": added, "skipped": [i["name"] for i in items if i["state"] == "free"]}


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------
def fetch_recipe(conn, recipe_id) -> dict:
    recipe = found(conn.execute("SELECT r.*, m.name AS model_name FROM paint_recipes r "
                                "LEFT JOIN models m USING (model_id) WHERE r.recipe_id = %s", (recipe_id,)).fetchone(),
                   f"Recipe {recipe_id}")
    steps = conn.execute("SELECT st.*, b.name AS brand FROM paint_recipe_steps st LEFT JOIN brands b USING (brand_id) "
                         "WHERE st.recipe_id = %s ORDER BY st.sort_order, st.step_id", (recipe_id,)).fetchall()
    steps = [{**s, **paint_state(conn, s["brand_id"], s["product_code"]), "name": s["paint_text"]} for s in steps]
    return {**recipe, "steps": steps, "check": summarise(steps)}


def _step_row(conn, tamiya, step: StepIn) -> dict:
    """A step as table columns: the paint linked to your supplies when it can be."""
    note, label, text = (step.note or "").strip() or None, (step.label or "").strip() or None, step.paint_text.strip()
    brand_id = code = None
    if step.supply_id is not None:
        s = found(conn.execute("SELECT brand_id, product_code, name FROM supplies WHERE supply_id = %s",
                               (step.supply_id,)).fetchone(), "Supply")
        brand_id, code, text = s["brand_id"], s["product_code"], text or s["name"]
    elif text:
        brand_id, code, shown = paints.resolve(conn, text, tamiya)
        if brand_id is None:                               # a name you own ("Mephiston Red")
            s = conn.execute("SELECT brand_id, product_code FROM supplies WHERE lower(name) = lower(%s) "
                             "AND product_code IS NOT NULL LIMIT 1", (text,)).fetchone()
            if s:
                brand_id, code = s["brand_id"], s["product_code"]
        elif shown is None:
            text = paints.default_name(conn, brand_id, code, text)
    if not text:
        raise HTTPException(422, "Each step needs a paint (pick one or type its name).")
    return {"label": label, "paint_text": text, "brand_id": brand_id, "product_code": code, "note": note}


def _set_steps(conn, recipe_id, steps: list[StepIn]):
    tamiya = tamiya_id_of(conn)
    rows = [_step_row(conn, tamiya, s) for s in steps]
    conn.execute("DELETE FROM paint_recipe_steps WHERE recipe_id = %s", (recipe_id,))
    for i, row in enumerate(rows):
        insert_row(conn, "paint_recipe_steps", {**row, "recipe_id": recipe_id, "sort_order": i}, "step_id")


def _check_model(conn, model_id):
    found(conn.execute("SELECT 1 FROM models WHERE model_id = %s", (model_id,)).fetchone(), "Model")


@router.get("/recipes")
def list_recipes(model_id: int | None = None):
    """Every recipe (or one model's), newest first, with whether you could paint it now."""
    with db() as conn:
        ids = conn.execute("SELECT recipe_id FROM paint_recipes WHERE (%(m)s::int IS NULL OR model_id = %(m)s) "
                           "ORDER BY created_at DESC, recipe_id DESC", {"m": model_id}).fetchall()
        return [fetch_recipe(conn, r["recipe_id"]) for r in ids]


@router.post("/recipes", status_code=201)
def add_recipe(body: RecipeIn):
    data = tidy_text({"name": body.name, "notes": body.notes, "model_id": body.model_id, "unit": body.unit})
    with db() as conn:
        if data["model_id"] is not None:
            _check_model(conn, data["model_id"])
        recipe_id = insert_row(conn, "paint_recipes", data, "recipe_id")
        _set_steps(conn, recipe_id, body.steps)
        return fetch_recipe(conn, recipe_id)


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    with db() as conn:
        return fetch_recipe(conn, recipe_id)


@router.patch("/recipes/{recipe_id}")
def update_recipe(recipe_id: int, body: RecipePatch):
    data = tidy_text(body.model_dump(exclude_unset=True, exclude={"steps"}))
    with db() as conn:
        fetch_recipe(conn, recipe_id)
        if data.get("model_id") is not None:
            _check_model(conn, data["model_id"])
        update_row(conn, "paint_recipes", "recipe_id", recipe_id, data)
        if body.steps is not None:
            _set_steps(conn, recipe_id, body.steps)
        return fetch_recipe(conn, recipe_id)


@router.delete("/recipes/{recipe_id}", status_code=204)
def delete_recipe(recipe_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM paint_recipes WHERE recipe_id = %s RETURNING recipe_id",
                           (recipe_id,)).fetchone(), f"Recipe {recipe_id}")
    return Response(status_code=204)


@router.post("/recipes/{recipe_id}/copy", status_code=201)
def copy_recipe(recipe_id: int, body: CopyIn | None = None):
    """Reuse a recipe: a copy on another model (or kept on its own)."""
    body = body or CopyIn()
    with db() as conn:
        src = fetch_recipe(conn, recipe_id)
        if body.model_id is not None:
            _check_model(conn, body.model_id)
        new_id = insert_row(conn, "paint_recipes", {"name": body.name or src["name"], "notes": src["notes"],
                                                    "model_id": body.model_id}, "recipe_id")
        for i, s in enumerate(src["steps"]):
            insert_row(conn, "paint_recipe_steps", {"recipe_id": new_id, "sort_order": i, "label": s["label"],
                                                    "paint_text": s["paint_text"], "brand_id": s["brand_id"],
                                                    "product_code": s["product_code"], "note": s["note"]}, "step_id")
        return fetch_recipe(conn, new_id)


# ---------------------------------------------------------------------------
# Can I paint this now?
# ---------------------------------------------------------------------------
@router.get("/recipes/{recipe_id}/paint-check")
def recipe_check(recipe_id: int):
    with db() as conn:
        recipe = fetch_recipe(conn, recipe_id)
        return {**recipe["check"], "items": recipe["steps"]}


@router.post("/recipes/{recipe_id}/paint-check/wishlist")
def recipe_to_wishlist(recipe_id: int):
    with db() as conn:
        recipe = fetch_recipe(conn, recipe_id)
        return to_wishlist(conn, recipe["steps"], f"For the recipe {recipe['name']}")


def model_items(conn, model_id) -> list[dict]:
    """A model's paint list as checkable lines (a mix counts as its parts; a paint you ticked by hand is owned)."""
    items = []
    for p in fetch_model(conn, model_id)["paints"]:
        parts = [{"name": x["paint_name"], "brand_id": x["brand_id"], "product_code": x["product_code"]}
                 for x in p["mix"]["parts"]] if p["mix"] else [{"name": p["paint_name"], "brand_id": p["brand_id"],
                                                               "product_code": p["product_code"]}]
        for x in parts:
            state = paint_state(conn, x["brand_id"], x["product_code"])
            if state["state"] in ("free", "missing") and p["have_it"] and not p["mix"]:
                state = {**state, "state": "owned"}            # ticked by hand
            items.append({**x, **state})
    return items


@router.get("/models/{model_id}/paint-check")
def model_check(model_id: int):
    with db() as conn:
        items = model_items(conn, model_id)
        return {**summarise(items), "items": items}


@router.post("/models/{model_id}/paint-check/wishlist")
def model_to_wishlist(model_id: int):
    with db() as conn:
        items = model_items(conn, model_id)
        name = fetch_model(conn, model_id)["name"]
        return to_wishlist(conn, items, f"For {name}")
