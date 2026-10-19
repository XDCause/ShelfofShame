"""Precision shooting: every shot in a group, and a session's photos and videos (74_shooting_shots_media.sql).

    POST   /shooting/groups/{id}/shots       a shot: where it landed (mm right / up of the aim), score, X, velocity,
                                             a called flyer - the group's size, centre, count, velocities and score
                                             are then worked out from its shots (recompute)
    PATCH / DELETE /shooting/shots/{id}      (the shots after a removed one move up a number)
    POST   /shooting/sessions/{id}/photos?group_id=&caption=   a photo (the body; shrunk by the browser)
    POST   /shooting/sessions/{id}/videos?group_id=&caption=   a video straight off the phone (the body, up to 4 GB),
                                             kept in <media>/videos like volleyball's, so the nightly backup has it
    GET    /shooting/media/{id}              the photo, or the video (seekable: Range requests)
    PATCH / DELETE /shooting/media/{id}      caption, which group it's of
Every call that changes something answers with the whole session (shooting_sessions.fetch_session).
"""
import secrets
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import shotmath
from .db import db, found, insert_row, tidy_text, update_row
from .images import photo_response, read_photo
from .volleyball import MAX_VIDEO_BYTES, VIDEO_TYPES, looks_like_video, remove_file, video_dir

router = APIRouter(prefix="/api", tags=["shooting"])


class ShotFields(BaseModel):
    x_mm: float | None = Field(None, ge=-100000, le=100000)
    y_mm: float | None = Field(None, ge=-100000, le=100000)
    score: float | None = Field(None, ge=0, le=1000)
    is_x: bool | None = None
    velocity: float | None = Field(None, gt=0, lt=3000)
    flyer: bool | None = None
    note: str | None = Field(None, max_length=500)


SHOT_SELECT = """SELECT shot_id, group_id, n, x_mm::float8 AS x_mm, y_mm::float8 AS y_mm, score::float8 AS score, is_x,
       velocity::float8 AS velocity, flyer, note FROM shooting_shots"""


def shots_by_group(conn, group_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {g: [] for g in group_ids}
    if group_ids:
        for s in conn.execute(SHOT_SELECT + " WHERE group_id = ANY(%s) ORDER BY group_id, n", (group_ids,)).fetchall():
            out[s["group_id"]].append(s)
    return out


def media_for(conn, session_id: int) -> list[dict]:
    return conn.execute("""SELECT media_id, session_id, group_id, kind, caption, file_type, file_size, original_name, created_at,
            '/api/shooting/media/' || media_id || '?v=' || (extract(epoch FROM created_at) * 1000)::bigint AS url
        FROM shooting_media WHERE session_id = %s ORDER BY created_at, media_id""", (session_id,)).fetchall()


def recompute(conn, group_id: int):
    """A group's numbers from its shots: count; size and centre from the placed shots that weren't flyers;
    velocities; score and X count. Numbers the shots don't have are left as you typed them."""
    shots = conn.execute(SHOT_SELECT + " WHERE group_id = %s ORDER BY n", (group_id,)).fetchall()
    if not shots:
        return
    data = {"shots": len(shots)}
    placed = [(s["x_mm"], s["y_mm"]) for s in shots if s["x_mm"] is not None and not s["flyer"]]
    stats = shotmath.group_stats(placed)
    if stats:
        data.update(up_mm=stats["up_mm"], right_mm=stats["right_mm"])
        if len(placed) >= 2:
            data["size_mm"] = stats["size_mm"]
    speeds = [s["velocity"] for s in shots if s["velocity"]]
    if speeds:
        data["velocities"] = speeds
    scored = [s for s in shots if s["score"] is not None]
    if scored:
        data.update(score=sum(s["score"] for s in scored), x_count=sum(1 for s in scored if s["is_x"]))
    update_row(conn, "shooting_groups", "group_id", group_id, data)


def _session_of_group(conn, group_id: int) -> int:
    return found(conn.execute("SELECT session_id FROM shooting_groups WHERE group_id = %s", (group_id,)).fetchone(), "Group")["session_id"]


def _answer(conn, session_id: int):
    from .shooting_sessions import fetch_session
    return fetch_session(conn, session_id)


@router.post("/shooting/groups/{group_id}/shots", status_code=201)
def add_shot(group_id: int, body: ShotFields):
    if (body.x_mm is None) != (body.y_mm is None):
        raise HTTPException(422, "A shot's place needs both how far right and how far up.")
    with db() as conn:
        session_id = _session_of_group(conn, group_id)
        n = conn.execute("SELECT COALESCE(max(n), 0) + 1 AS n FROM shooting_shots WHERE group_id = %s", (group_id,)).fetchone()["n"]
        data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
        insert_row(conn, "shooting_shots", {**data, "group_id": group_id, "n": n}, "shot_id")
        recompute(conn, group_id)
        return _answer(conn, session_id)


@router.patch("/shooting/shots/{shot_id}")
def update_shot(shot_id: int, body: ShotFields):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    for required in ("is_x", "flyer"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} must be true or false.")
    with db() as conn:
        s = found(conn.execute("SELECT group_id FROM shooting_shots WHERE shot_id = %s", (shot_id,)).fetchone(), "Shot")
        update_row(conn, "shooting_shots", "shot_id", shot_id, data)
        recompute(conn, s["group_id"])
        return _answer(conn, _session_of_group(conn, s["group_id"]))


@router.delete("/shooting/shots/{shot_id}")
def delete_shot(shot_id: int):
    with db() as conn:
        s = found(conn.execute("DELETE FROM shooting_shots WHERE shot_id = %s RETURNING group_id, n", (shot_id,)).fetchone(), "Shot")
        conn.execute("UPDATE shooting_shots SET n = n - 1 WHERE group_id = %s AND n > %s", (s["group_id"], s["n"]))
        left = conn.execute("SELECT count(*) AS c FROM shooting_shots WHERE group_id = %s", (s["group_id"],)).fetchone()["c"]
        if left:
            recompute(conn, s["group_id"])
        return _answer(conn, _session_of_group(conn, s["group_id"]))


# ---------------------------------------------------------------------------------------------
# Photos and videos
# ---------------------------------------------------------------------------------------------
def _check_group(conn, session_id: int, group_id: int | None):
    if group_id is not None and not conn.execute("SELECT 1 FROM shooting_groups WHERE group_id = %s AND session_id = %s",
                                                 (group_id, session_id)).fetchone():
        raise HTTPException(422, "That group isn't in this session.")


@router.post("/shooting/sessions/{session_id}/photos", status_code=201)
async def add_photo(session_id: int, request: Request, group_id: int | None = None,
                    caption: str | None = Query(None, max_length=500)):
    image, image_type = await read_photo(request)
    with db() as conn:
        found(conn.execute("SELECT 1 FROM shooting_sessions WHERE session_id = %s", (session_id,)).fetchone(), "Session")
        _check_group(conn, session_id, group_id)
        insert_row(conn, "shooting_media", {"session_id": session_id, "group_id": group_id, "kind": "photo", "photo": image,
                                            "photo_type": image_type, "caption": (caption or "").strip() or None}, "media_id")
        return _answer(conn, session_id)


@router.post("/shooting/sessions/{session_id}/videos", status_code=201)
async def add_video(session_id: int, request: Request, group_id: int | None = None,
                    caption: str | None = Query(None, max_length=500)):
    """A video, as the request body (Content-Type video/mp4, video/quicktime...; up to 4 GB), written to disk as it arrives."""
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind not in VIDEO_TYPES:
        raise HTTPException(415, "That isn't a video this app can keep (MP4, MOV, WebM or MKV).")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM shooting_sessions WHERE session_id = %s", (session_id,)).fetchone(), "Session")
        _check_group(conn, session_id, group_id)
    name = f"shoot-{session_id}-{secrets.token_hex(6)}.{VIDEO_TYPES[kind]}"
    part = video_dir() / (name + ".part")
    size, head = 0, b""
    try:
        with open(part, "wb") as f:
            async for chunk in request.stream():
                if len(head) < 16:
                    head += chunk[:16]
                size += len(chunk)
                if size > MAX_VIDEO_BYTES:
                    raise HTTPException(413, "Videos can be up to 4 GB.")
                f.write(chunk)
        if size == 0 or not looks_like_video(head):
            raise HTTPException(422, "That file doesn't look like a video.")
        part.rename(video_dir() / name)
    finally:
        part.unlink(missing_ok=True)
    try:
        with db() as conn:
            insert_row(conn, "shooting_media", {"session_id": session_id, "group_id": group_id, "kind": "video", "file_name": name,
                                                "file_type": kind, "file_size": size, "caption": (caption or "").strip() or None,
                                                "original_name": unquote(request.headers.get("x-file-name", ""))[:200] or None},
                       "media_id")
            return _answer(conn, session_id)
    except Exception:
        remove_file(name)              # the session went while it uploaded: don't leave the file behind
        raise


@router.get("/shooting/media/{media_id}")
def get_media(media_id: int):
    with db() as conn:
        m = found(conn.execute("SELECT kind, photo, photo_type, file_name, file_type FROM shooting_media WHERE media_id = %s",
                               (media_id,)).fetchone(), "Photo or video")
    if m["kind"] == "photo":
        return photo_response(m["photo"], m["photo_type"])
    path = video_dir() / (m["file_name"] or "")
    if not m["file_name"] or not path.is_file():
        raise HTTPException(404, "No video file.")
    return FileResponse(path, media_type=m["file_type"], headers={
        "Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"})


class MediaPatch(BaseModel):
    caption: str | None = Field(None, max_length=500)
    group_id: int | None = None


@router.patch("/shooting/media/{media_id}")
def update_media(media_id: int, body: MediaPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    with db() as conn:
        m = found(conn.execute("SELECT session_id FROM shooting_media WHERE media_id = %s", (media_id,)).fetchone(), "Photo or video")
        if data.get("group_id") is not None:
            _check_group(conn, m["session_id"], data["group_id"])
        update_row(conn, "shooting_media", "media_id", media_id, data)
        return _answer(conn, m["session_id"])


@router.delete("/shooting/media/{media_id}")
def delete_media(media_id: int):
    with db() as conn:
        m = found(conn.execute("DELETE FROM shooting_media WHERE media_id = %s RETURNING session_id, file_name",
                               (media_id,)).fetchone(), "Photo or video")
        answer = _answer(conn, m["session_id"])
    remove_file(m["file_name"])
    return answer


