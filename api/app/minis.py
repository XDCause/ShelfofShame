"""Each mini in a Warhammer box with its own build step, so a box of 19 can be 5 painted, 10 primed
and 4 still on the sprue.

A box's minis are set up from what's in it (product_info.kit_units, read from Good Games' description:
"1x Tech-Priest Enginseer, 10x Skitarii Rangers...") or added by hand ("10 Skitarii Rangers").
Once a box has minis, the box itself follows them (sync):
    stage         = the step EVERY mini has reached (the furthest the whole box has got)
    figures       = how many minis; figures_done = how many are Complete
    status        = In progress as soon as any mini has a step; Finished when all are Complete
                    (models.tidy_model's rules)
Ticking a step for the whole box (the box's own steps, a journal suggestion, marking it Finished)
brings every mini that's behind up to it (after_model_change).
"""
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import goodgames, warhammer
from .db import STAGES, db, found, update_row
from .models import NOT_STARTED, date_status, fetch_model, tidy_model

router = APIRouter(prefix="/api", tags=["models"])

MAX_MINIS = 200


class MinisIn(BaseModel):
    unit: str = Field(min_length=1, max_length=80)
    count: int = Field(1, ge=1, le=100)


class MiniPatch(BaseModel):
    stage: str | None = None
    name: str | None = Field(None, max_length=60)
    unit: str | None = Field(None, min_length=1, max_length=80)


class StageIn(BaseModel):
    mini_ids: list[int] = Field(min_length=1)
    stage: str | None = None


class UnitRename(BaseModel):
    unit: str = Field(min_length=1, max_length=80)
    to: str = Field(min_length=1, max_length=80)


def _model(conn, model_id: int) -> dict:
    return found(conn.execute("SELECT model_id, hobby, product_code, brand_id FROM models WHERE model_id = %s",
                              (model_id,)).fetchone(), f"Model {model_id}")


def _check_stage(hobby: str, stage: str | None):
    if stage is not None and stage not in STAGES[hobby]:
        raise HTTPException(422, f"'{stage}' isn't a {hobby} build step. Steps: {', '.join(STAGES[hobby])}.")


def _add(conn, model_id: int, units: list[dict]):
    have = conn.execute("SELECT count(*) AS n, COALESCE(max(sort_order), 0) AS last FROM model_minis WHERE model_id = %s",
                        (model_id,)).fetchone()
    if have["n"] + sum(u["count"] for u in units) > MAX_MINIS:
        raise HTTPException(422, f"That's more than {MAX_MINIS} minis in one box.")
    order = have["last"]
    for u in units:
        for _ in range(u["count"]):
            order += 1
            conn.execute("INSERT INTO model_minis (model_id, unit, sort_order) VALUES (%s, %s, %s)",
                         (model_id, u["unit"].strip(), order))


def sync(conn, model_id: int):
    """The box follows its minis (see the module docstring). Nothing changes for a box without minis."""
    model = fetch_model(conn, model_id)
    minis = model["minis"]
    if not minis:
        return
    steps = STAGES[model["hobby"]]
    at = [steps.index(m["stage"]) if m["stage"] in steps else -1 for m in minis]
    low = min(at)
    data = {"stage": steps[low] if low >= 0 else None, "skipped_steps": [],
            "figures": len(minis), "figures_done": sum(1 for i in at if i == len(steps) - 1)}
    if max(at) >= 0 and low < 0 and model["status"] in NOT_STARTED:
        data["status"] = "In progress"                     # one mini primed = the box is started
    if data["stage"] is None and model["stage"] is None and model["status"] != "Finished":
        data.pop("stage")
    data = tidy_model(conn, model, data)
    update_row(conn, "models", "model_id", model_id, data)
    date_status(conn, model_id, data.get("status"))


def after_model_change(conn, model_id: int, data: dict):
    """A step ticked for the whole box: minis behind it catch up. Then the box follows its minis again."""
    if not conn.execute("SELECT 1 FROM model_minis WHERE model_id = %s LIMIT 1", (model_id,)).fetchone():
        return
    stage = data.get("stage")
    steps = STAGES[_model(conn, model_id)["hobby"]]
    if stage:
        conn.execute("""UPDATE model_minis SET stage = %(stage)s, updated_at = now()
                        WHERE model_id = %(id)s AND (stage IS NULL OR array_position(%(steps)s, stage) < %(at)s)""",
                     {"stage": stage, "id": model_id, "steps": steps, "at": steps.index(stage) + 1})
    if data.get("status") and data["status"] != "Finished" and "stage" in data and stage != steps[-1]:
        # Un-finished: the Complete minis go back to the box's step (or else the box would be Finished again).
        conn.execute("UPDATE model_minis SET stage = %s, updated_at = now() WHERE model_id = %s AND stage = %s",
                     (stage, model_id, steps[-1]))
    sync(conn, model_id)


@router.post("/models/{model_id}/minis", status_code=201)
def add_minis(model_id: int, body: MinisIn):
    """Add minis by hand: "10 Skitarii Rangers" = unit Skitarii Rangers, count 10."""
    with db() as conn:
        _model(conn, model_id)
        _add(conn, model_id, [{"unit": body.unit, "count": body.count}])
        sync(conn, model_id)
        return fetch_model(conn, model_id)


@router.post("/models/{model_id}/minis/from-box", status_code=201)
def minis_from_box(model_id: int):
    """Set up the minis from what's in the box (asks Good Games by the GW code if it hasn't been read yet)."""
    with db() as conn:
        model = _model(conn, model_id)
        if conn.execute("SELECT 1 FROM model_minis WHERE model_id = %s LIMIT 1", (model_id,)).fetchone():
            raise HTTPException(409, "This box's minis are already set up.")
        row = conn.execute("SELECT kit_units FROM product_info WHERE brand_id = %s AND product_code = %s",
                           (model["brand_id"], model["product_code"])).fetchone()
    units = row and row["kit_units"]
    if not units and model["product_code"] and goodgames.GW_CODE.fullmatch(f"({model['product_code']})"):
        picked = warhammer._shop(warhammer._pick, model["product_code"])
        if isinstance(picked, dict):
            warhammer._store(picked)
            units = picked["units"]
    if not units:
        raise HTTPException(404, "The shop's description doesn't say what's in the box - add the minis by hand.")
    with db() as conn:
        _add(conn, model_id, units)
        sync(conn, model_id)
        return fetch_model(conn, model_id)


@router.patch("/model-minis/{mini_id}")
def update_mini(mini_id: int, body: MiniPatch):
    """One mini's step (null = not started), name ("Alpha", "Plasma caliver") or unit."""
    data = body.model_dump(exclude_unset=True)
    with db() as conn:
        mini = found(conn.execute("SELECT model_id FROM model_minis WHERE mini_id = %s", (mini_id,)).fetchone(), "Mini")
        if "stage" in data:
            _check_stage(_model(conn, mini["model_id"])["hobby"], data["stage"])
        if "name" in data:
            data["name"] = (data["name"] or "").strip() or None
        if data.get("unit"):
            data["unit"] = data["unit"].strip()
        update_row(conn, "model_minis", "mini_id", mini_id, data)
        conn.execute("UPDATE model_minis SET updated_at = now() WHERE mini_id = %s", (mini_id,))
        sync(conn, mini["model_id"])
        return fetch_model(conn, mini["model_id"])


@router.put("/models/{model_id}/minis/stage")
def set_stage(model_id: int, body: StageIn):
    """Several minis to one step at once (a whole unit primed)."""
    with db() as conn:
        _check_stage(_model(conn, model_id)["hobby"], body.stage)
        changed = conn.execute("UPDATE model_minis SET stage = %s, updated_at = now() WHERE model_id = %s AND mini_id = ANY(%s)",
                               (body.stage, model_id, body.mini_ids)).rowcount
        if changed != len(set(body.mini_ids)):
            raise HTTPException(404, "Some of those minis aren't in this box.")
        sync(conn, model_id)
        return fetch_model(conn, model_id)


@router.put("/models/{model_id}/minis/unit")
def rename_unit(model_id: int, body: UnitRename):
    """Rename a unit (every mini in it)."""
    with db() as conn:
        found(conn.execute("UPDATE model_minis SET unit = %s WHERE model_id = %s AND unit = %s RETURNING model_id",
                           (body.to.strip(), model_id, body.unit)).fetchone(), "That unit")
        return fetch_model(conn, model_id)


@router.delete("/model-minis/{mini_id}", status_code=204)
def delete_mini(mini_id: int):
    with db() as conn:
        mini = found(conn.execute("DELETE FROM model_minis WHERE mini_id = %s RETURNING model_id", (mini_id,)).fetchone(), "Mini")
        sync(conn, mini["model_id"])
    return Response(status_code=204)


@router.delete("/models/{model_id}/minis", status_code=204)
def delete_unit(model_id: int, unit: str):
    """Remove a whole unit's minis."""
    with db() as conn:
        found(conn.execute("DELETE FROM model_minis WHERE model_id = %s AND unit = %s RETURNING model_id",
                           (model_id, unit)).fetchone(), "That unit")
        sync(conn, model_id)
    return Response(status_code=204)
