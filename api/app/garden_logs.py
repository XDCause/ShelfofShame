"""Gardening: logs (notes, harvests, problems, measurements) with their photos - a photo timeline - and your own
tasks (reminders, once or repeating). Split out of garden.py (health check, 2026-10-21)."""

from datetime import date
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .images import photo_response, read_photo
from .garden import LOG_KINDS, LOG_SELECT, TASK_SELECT, _lit

router = APIRouter(prefix="/api", tags=["gardening"])


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
