"""Colour matches and mixes.

Matches come from three places, most certain first:
  same code   Tamiya's colour codes are the same colour in every range: X-7 is X-7 as an
              Acrylic Mini, an enamel or a big jar. Worked out from the Tamiya catalogue.
  same name   different Tamiya ranges with the same colour name - LP-28, TS-5 and XF-62 are all
              "Olive Drab". Likely close, not guaranteed: a hint, labelled as one.
  your match  colour groups you've made (any brand, e.g. from a kit's instructions), with a
              note of where the match came from.
Cross-brand conversion charts aren't built in: the ones online are other people's work with no
licence to copy, and every chart says matches are approximate anyway.

Mixes are your recipes ("XF-62 + XF-2 (3:1)"). A model's checklist line can be a mix; you
"have" it when you own every part.
"""
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import paints, tamiya
from .db import brand_id as brand_named, db, found, update_row

router = APIRouter(prefix="/api", tags=["colours"])


# ---------------------------------------------------------------------------
# What colour things are
# ---------------------------------------------------------------------------
def _catalogue(conn) -> list[dict]:
    """Tamiya paints in the catalogue, with their colour. Generic pages (items like 'X7' that
    aren't a bottle you can buy) are left out."""
    rows = conn.execute("""
        SELECT c.brand_id, c.product_code, c.item, c.title, c.thumb_url,
               s.supply_id AS owned_supply_id, COALESCE(s.qty_on_hand, 0) AS owned_qty
        FROM catalog_products c
        LEFT JOIN supplies s ON s.brand_id = c.brand_id AND s.product_code = c.product_code
        WHERE c.item ~ '^[0-9]+$'""").fetchall()
    out = []
    for r in rows:
        colour = tamiya.colour_of(r["title"])
        if colour:
            out.append({**r, "code": colour[0], "colour": colour[1], "name": tamiya.your_style_name(r["title"])})
    return out


def _owned(conn) -> list[dict]:
    """Supplies you have (qty > 0), with their colour when it can be worked out."""
    rows = conn.execute("""
        SELECT s.supply_id, s.brand_id, s.product_code, s.name, s.qty_on_hand,
               COALESCE(p.title, c.title) AS title
        FROM supplies s
        LEFT JOIN product_info p ON p.brand_id = s.brand_id AND p.product_code = s.product_code
        LEFT JOIN catalog_products c ON c.brand_id = s.brand_id AND c.product_code = s.product_code
        WHERE s.qty_on_hand > 0""").fetchall()
    return [{**r, "colour": tamiya.colour_of(r["title"]) or tamiya.colour_of(r["name"])} for r in rows]


def colour_for(conn, brand_id, product_code, name=None):
    """(code, colour name) for one product, from its title (or the name you gave it)."""
    row = conn.execute("""
        SELECT COALESCE(p.title, c.title) AS title FROM (SELECT %(b)s::int AS b, %(c)s::text AS c) x
        LEFT JOIN product_info p ON p.brand_id = x.b AND p.product_code = x.c
        LEFT JOIN catalog_products c ON c.brand_id = x.b AND c.product_code = x.c""",
        {"b": brand_id, "c": product_code}).fetchone()
    return tamiya.colour_of(row and row["title"]) or tamiya.colour_of(name)


def _groups_with(conn, brand_id, product_code) -> list[dict]:
    ids = [r["group_id"] for r in conn.execute(
        "SELECT DISTINCT group_id FROM colour_group_members WHERE brand_id = %s AND product_code = %s",
        (brand_id, product_code)).fetchall()]
    return [fetch_group(conn, i) for i in ids]


def _one_per_code(entries: list[dict]) -> list[dict]:
    """Several bottles share a code (Mini, enamel, jar): show one each - the one you own, else
    the Acrylic Mini, else the lowest item number."""
    best = {}
    for e in entries:
        rank = (e["owned_qty"] <= 0, not e["item"].startswith(("815", "817")), e["item"])
        if e["code"] not in best or rank < best[e["code"]][0]:
            best[e["code"]] = (rank, e)
    return [e for _, e in sorted(best.values(), key=lambda x: x[1]["code"])]


@router.get("/colours/matches")
def matches(brand_id: int, product_code: str, name: str | None = None):
    """Other paints that are (or are probably) the same colour as this one."""
    with db() as conn:
        colour = colour_for(conn, brand_id, product_code, name)
        same_code, same_name = [], []
        if colour:
            code, colour_name = colour
            for e in _catalogue(conn):
                if e["product_code"] == product_code:
                    continue
                if e["code"] == code:
                    same_code.append(e)
                elif e["colour"] == colour_name:
                    same_name.append(e)
        same_code.sort(key=lambda e: (e["owned_qty"] <= 0, e["item"]))
        return {"colour": {"code": colour[0], "name": tamiya.nice_name(colour[1])} if colour else None,
                "same_code": same_code, "same_name": _one_per_code(same_name),
                "groups": _groups_with(conn, brand_id, product_code)}


def owned_alternatives(conn, wanted: list[dict]) -> dict:
    """For checklist paints you don't have: something you DO own that matches.
    `wanted` = [{key, brand_id, product_code, paint_name}] -> {key: {supply_id, name, how}}."""
    if not wanted:
        return {}
    owned = _owned(conn)
    groups = conn.execute("SELECT group_id, brand_id, product_code FROM colour_group_members").fetchall()
    found_alt = {}
    for w in wanted:
        colour = colour_for(conn, w["brand_id"], w["product_code"], w["paint_name"])
        mine = {g["group_id"] for g in groups
                if g["brand_id"] == w["brand_id"] and g["product_code"] == w["product_code"] and w["product_code"]}
        partners = {(g["brand_id"], g["product_code"]) for g in groups if g["group_id"] in mine}
        for o in owned:
            if o["brand_id"] == w["brand_id"] and o["product_code"] == w["product_code"]:
                continue
            how = None
            if (o["brand_id"], o["product_code"]) in partners:
                how = "your match"
            elif colour and o["colour"] and o["colour"][0] == colour[0]:
                how = f"same colour ({colour[0]})"
            elif colour and o["colour"] and o["colour"][1] == colour[1]:
                how = f"same name ({tamiya.nice_name(colour[1])})"
            if how:
                found_alt[w["key"]] = {"supply_id": o["supply_id"], "name": o["name"], "how": how}
                break
    return found_alt


# ---------------------------------------------------------------------------
# Your colour groups ("these are the same colour")
# ---------------------------------------------------------------------------
class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    note: str | None = None
    paints: str = Field(min_length=1, description="One paint per line: XF-62, Mr. Color C38, ...")


class GroupPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    note: str | None = None
    paints: str | None = None


GROUP_MEMBERS = """
SELECT g.*, b.name AS brand, s.supply_id AS owned_supply_id, COALESCE(s.qty_on_hand, 0) AS owned_qty
FROM colour_group_members g
LEFT JOIN brands b ON b.brand_id = g.brand_id
LEFT JOIN supplies s ON s.brand_id = g.brand_id AND s.product_code = g.product_code
WHERE g.group_id = %s ORDER BY g.sort_order, g.member_id"""


def fetch_group(conn, group_id):
    group = found(conn.execute("SELECT * FROM colour_groups WHERE group_id = %s", (group_id,)).fetchone(),
                  "Colour match")
    return {**group, "members": conn.execute(GROUP_MEMBERS, (group_id,)).fetchall()}


def _set_members(conn, group_id, text):
    conn.execute("DELETE FROM colour_group_members WHERE group_id = %s", (group_id,))
    tamiya_id = brand_named(conn, "Tamiya")
    lines = [paints.parse_line(ln)[0] for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise HTTPException(422, "A match needs at least two paints, one per line.")
    for order, line in enumerate(lines, 1):
        p = paints.to_product(conn, line, tamiya_id)
        conn.execute("INSERT INTO colour_group_members (group_id, brand_id, product_code, paint_name, sort_order) "
                     "VALUES (%s, %s, %s, %s, %s)", (group_id, p["brand_id"], p["product_code"],
                                                     p["paint_name"], order))


@router.get("/colour-groups")
def list_groups():
    with db() as conn:
        ids = conn.execute("SELECT group_id FROM colour_groups ORDER BY name").fetchall()
        return [fetch_group(conn, r["group_id"]) for r in ids]


@router.post("/colour-groups", status_code=201)
def add_group(body: GroupIn):
    with db() as conn:
        group_id = conn.execute("INSERT INTO colour_groups (name, note) VALUES (%s, %s) RETURNING group_id",
                                (body.name.strip(), body.note)).fetchone()["group_id"]
        _set_members(conn, group_id, body.paints)
        return fetch_group(conn, group_id)


@router.patch("/colour-groups/{group_id}")
def change_group(group_id: int, body: GroupPatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        fetch_group(conn, group_id)
        if "paints" in data:
            _set_members(conn, group_id, data.pop("paints") or "")
        update_row(conn, "colour_groups", "group_id", group_id, data)
        return fetch_group(conn, group_id)


@router.delete("/colour-groups/{group_id}", status_code=204)
def delete_group(group_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM colour_groups WHERE group_id = %s RETURNING group_id",
                           (group_id,)).fetchone(), "Colour match")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Mixes
# ---------------------------------------------------------------------------
class MixIn(BaseModel):
    name: str | None = Field(None, max_length=100)  # blank = the recipe itself
    recipe: str = Field(min_length=1, description='e.g. "XF-62 + XF-2 (3:1)"')
    notes: str | None = None


class MixPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    recipe: str | None = Field(None, min_length=1)
    notes: str | None = None


MIX_PARTS = """
SELECT x.*, b.name AS brand, s.supply_id AS owned_supply_id, COALESCE(s.qty_on_hand, 0) AS owned_qty
FROM mix_parts x
LEFT JOIN brands b ON b.brand_id = x.brand_id
LEFT JOIN supplies s ON s.brand_id = x.brand_id AND s.product_code = x.product_code
WHERE x.mix_id = %s ORDER BY x.sort_order, x.part_id"""

# SQL: does the mix in column {col} have every part in stock?
MIX_COMPLETE = """(NOT EXISTS (SELECT 1 FROM mix_parts x
                       WHERE x.mix_id = {col} AND NOT EXISTS (
                           SELECT 1 FROM supplies s WHERE s.brand_id = x.brand_id
                           AND s.product_code = x.product_code AND s.qty_on_hand > 0)))"""


def fetch_mix(conn, mix_id):
    mix = found(conn.execute("SELECT * FROM mixes WHERE mix_id = %s", (mix_id,)).fetchone(), "Mix")
    parts = conn.execute(MIX_PARTS, (mix_id,)).fetchall()
    used_on = conn.execute("SELECT DISTINCT m.model_id, m.name FROM model_paints mp JOIN models m USING (model_id) "
                           "WHERE mp.mix_id = %s ORDER BY m.name", (mix_id,)).fetchall()
    return {**mix, "parts": parts, "have_all": all(p["owned_qty"] > 0 for p in parts),
            "recipe": recipe_text(parts), "short": recipe_text(parts, short=True), "used_on": used_on}


def recipe_text(parts, short=False) -> str:
    """[XF-62 x3, XF-2 x1] -> 'Acrylic XF62 Olive Drab + Acrylic XF2 Flat White (3:1)',
    or with short=True 'XF-62 + XF-2 (3:1)' (how you'd type it)."""
    def label(p):
        colour = tamiya.colour_of(p["paint_name"]) if short else None
        return colour[0] if colour else p["paint_name"]
    text = " + ".join(label(p) for p in parts)
    amounts = [p["parts"] for p in parts]
    if any(a != 1 for a in amounts):
        text += " (" + ":".join(f"{a.normalize():f}" for a in amounts) + ")"
    return text


def create_mix(conn, recipe: str, name: str | None = None, notes: str | None = None) -> int:
    mix_id = conn.execute("INSERT INTO mixes (name, notes) VALUES (%s, %s) RETURNING mix_id",
                          ((name or "").strip() or recipe.strip(), notes)).fetchone()["mix_id"]
    _set_parts(conn, mix_id, recipe)
    return mix_id


def _set_parts(conn, mix_id, recipe):
    parts = paints.parse_mix(recipe)
    if len(parts) < 2:
        raise HTTPException(422, 'A mix needs at least two paints, e.g. "XF-62 + XF-2 (3:1)".')
    conn.execute("DELETE FROM mix_parts WHERE mix_id = %s", (mix_id,))
    tamiya_id = brand_named(conn, "Tamiya")
    for order, (typed, amount) in enumerate(parts, 1):
        p = paints.to_product(conn, typed, tamiya_id)
        conn.execute("INSERT INTO mix_parts (mix_id, brand_id, product_code, paint_name, parts, sort_order) "
                     "VALUES (%s, %s, %s, %s, %s, %s)",
                     (mix_id, p["brand_id"], p["product_code"], p["paint_name"], amount, order))


@router.get("/mixes")
def list_mixes():
    with db() as conn:
        ids = conn.execute("SELECT mix_id FROM mixes ORDER BY name").fetchall()
        return [fetch_mix(conn, r["mix_id"]) for r in ids]


@router.post("/mixes", status_code=201)
def add_mix(body: MixIn):
    with db() as conn:
        return fetch_mix(conn, create_mix(conn, body.recipe, body.name, body.notes))


@router.patch("/mixes/{mix_id}")
def change_mix(mix_id: int, body: MixPatch):
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        fetch_mix(conn, mix_id)
        if "recipe" in data:
            _set_parts(conn, mix_id, data.pop("recipe"))
        update_row(conn, "mixes", "mix_id", mix_id, data)
        return fetch_mix(conn, mix_id)


@router.delete("/mixes/{mix_id}", status_code=204)
def delete_mix(mix_id: int):
    """Model checklist lines that used it keep their name but stop being a mix."""
    with db() as conn:
        found(conn.execute("DELETE FROM mixes WHERE mix_id = %s RETURNING mix_id", (mix_id,)).fetchone(), "Mix")
    return Response(status_code=204)
