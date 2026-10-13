"""Drawings in the journal: pen sketches, whiteboards, pictures on a canvas (Excalidraw).

A drawing belongs to a journal page: either a Drawing block on a notes page, or the whole page of
a whiteboard page (board = true). The browser saves it in three parts, so each request stays small:
    scene     the shapes and pen strokes (PUT /journal/drawings/{id}), saved a moment after you stop
    files     pictures dropped onto the canvas, sent once each (PUT .../files merges them in)
    preview   a PNG of the whole drawing, for the page and the journal list (PUT .../preview)
Words written with the text tool are kept in `text`, and the page's searchable text includes them.
"""
from fastapi import APIRouter, HTTPException, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .db import db, found, insert_row
from .images import photo_response, read_photo
from .journal_text import plain_text

router = APIRouter(prefix="/api", tags=["journal"])

MAX_FILE_CHARS = 8 * 1024 * 1024      # one picture as a data: URL (a 5 MB photo is ~6.7 MB as text)
# Drawings no block points at any more are removed when the page is next saved - unless they were
# changed in the last few minutes (a block being added, or undo bringing a deleted one back).
ORPHAN_GRACE = "10 minutes"


class SceneIn(BaseModel):
    elements: list = []
    app_state: dict = Field(default_factory=dict)   # just what's worth keeping: background, grid


class FileIn(BaseModel):
    mimeType: str = Field(pattern=r"^image/(png|jpeg|webp|gif|svg\+xml)$")
    dataURL: str = Field(pattern=r"^data:image/", max_length=MAX_FILE_CHARS)


def preview_url(row) -> str | None:
    if not row["has_preview"]:
        return None
    return f"/api/journal/drawings/{row['drawing_id']}/preview?v={row['version']}"


# `version` (updated_at in milliseconds) is worked out by the database, exactly as the journal
# list does for its pictures (journal.PAGE_LIST), so both give the same address for a preview.
DRAWING_META = """SELECT drawing_id, page_id, board, text, preview IS NOT NULL AS has_preview, created_at, updated_at,
                         (extract(epoch FROM updated_at) * 1000)::bigint AS version
                  FROM journal_drawings"""


def meta(row: dict) -> dict:
    return {**{k: v for k, v in row.items() if k not in ("has_preview", "version")}, "preview_url": preview_url(row)}


def page_drawings(conn, page_id: int) -> list[dict]:
    """A page's drawings, without their (big) scenes."""
    return [meta(r) for r in conn.execute(DRAWING_META + " WHERE page_id = %s ORDER BY board DESC, drawing_id",
                                          (page_id,)).fetchall()]


def drawing_ids_in(blocks) -> set[int]:
    """The drawings a page's blocks show ({"type": "drawing", "props": {"drawingId": "7"}})."""
    ids = set()
    for block in blocks or []:
        if isinstance(block, dict):
            ref = str(block.get("props", {}).get("drawingId", "")) if block.get("type") == "drawing" else ""
            if ref.isdigit():
                ids.add(int(ref))
            ids |= drawing_ids_in(block.get("children"))
    return ids


def drop_unused(conn, page_id: int, blocks: list):
    """Delete the page's sketches its blocks no longer show (not the whiteboard, nor recent ones)."""
    conn.execute(f"DELETE FROM journal_drawings WHERE page_id = %s AND NOT board AND NOT drawing_id = ANY(%s) "
                 f"AND updated_at < now() - interval '{ORPHAN_GRACE}'", (page_id, list(drawing_ids_in(blocks))))


def page_text(conn, page_id: int, blocks: list) -> str:
    """Everything searchable on a page: its blocks' words, then the words on its drawings."""
    drawn = [r["text"] for r in conn.execute("SELECT text FROM journal_drawings WHERE page_id = %s AND text <> '' "
                                             "ORDER BY board DESC, drawing_id", (page_id,)).fetchall()]
    return "\n".join(t for t in [plain_text(blocks), *drawn] if t)


def scene_text(elements: list) -> str:
    """The words written on a canvas with the text tool, top to bottom."""
    texts = [e for e in elements if isinstance(e, dict) and e.get("type") == "text" and not e.get("isDeleted")]
    texts.sort(key=lambda e: (e.get("y", 0), e.get("x", 0)))
    return "\n".join(str(e.get("originalText") or e.get("text") or "").strip() for e in texts).strip()


def fetch_drawing(conn, drawing_id: int) -> dict:
    return found(conn.execute(DRAWING_META + " WHERE drawing_id = %s", (drawing_id,)).fetchone(), "Drawing")


def refresh_page_text(conn, page_id: int):
    content = conn.execute("SELECT content FROM journal_pages WHERE page_id = %s", (page_id,)).fetchone()["content"]
    conn.execute("UPDATE journal_pages SET text = %s WHERE page_id = %s", (page_text(conn, page_id, content), page_id))


def add_drawing(conn, page_id: int, board: bool = False) -> dict:
    drawing_id = insert_row(conn, "journal_drawings", {"page_id": page_id, "board": board}, "drawing_id")
    return meta(fetch_drawing(conn, drawing_id))


@router.post("/journal/{page_id}/drawings", status_code=201)
def new_drawing(page_id: int):
    """A new, empty sketch for a Drawing block on this page."""
    with db() as conn:
        found(conn.execute("SELECT 1 FROM journal_pages WHERE page_id = %s", (page_id,)).fetchone(), "Journal page")
        return add_drawing(conn, page_id)


@router.get("/journal/drawings/{drawing_id}")
def get_drawing(drawing_id: int):
    """Everything needed to open the canvas: the scene and the pictures on it."""
    with db() as conn:
        row = fetch_drawing(conn, drawing_id)
        full = conn.execute("SELECT scene, files FROM journal_drawings WHERE drawing_id = %s", (drawing_id,)).fetchone()
        return {**meta(row), **full}


@router.put("/journal/drawings/{drawing_id}")
def save_scene(drawing_id: int, body: SceneIn):
    """Save the shapes and strokes (deleted ones are dropped) and the words written on them."""
    elements = [e for e in body.elements if isinstance(e, dict) and not e.get("isDeleted")]
    keep = {k: body.app_state[k] for k in ("viewBackgroundColor", "gridSize", "gridModeEnabled") if k in body.app_state}
    with db() as conn:
        row = fetch_drawing(conn, drawing_id)
        conn.execute("UPDATE journal_drawings SET scene = %s, text = %s WHERE drawing_id = %s",
                     (Jsonb({"elements": elements, "appState": keep}), scene_text(elements), drawing_id))
        refresh_page_text(conn, row["page_id"])
        return meta(fetch_drawing(conn, drawing_id))


@router.put("/journal/drawings/{drawing_id}/files")
def add_files(drawing_id: int, files: dict[str, FileIn]):
    """Pictures dropped onto the canvas, by Excalidraw's file id. Sent once each; merged in."""
    if len(files) > 20:
        raise HTTPException(413, "Send at most 20 pictures at a time.")
    with db() as conn:
        fetch_drawing(conn, drawing_id)
        conn.execute("UPDATE journal_drawings SET files = files || %s WHERE drawing_id = %s",
                     (Jsonb({k: v.model_dump() for k, v in files.items()}), drawing_id))
        return meta(fetch_drawing(conn, drawing_id))


@router.put("/journal/drawings/{drawing_id}/preview")
async def save_preview(drawing_id: int, request: Request):
    """A PNG of the drawing (the request body), shown on the page and in the journal list."""
    image, image_type = await read_photo(request)
    with db() as conn:
        found(conn.execute("UPDATE journal_drawings SET preview = %s, preview_type = %s WHERE drawing_id = %s "
                           "RETURNING drawing_id", (image, image_type, drawing_id)).fetchone(), "Drawing")
        return meta(fetch_drawing(conn, drawing_id))


@router.get("/journal/drawings/{drawing_id}/preview")
def get_preview(drawing_id: int):
    with db() as conn:
        row = found(conn.execute("SELECT preview, preview_type FROM journal_drawings WHERE drawing_id = %s",
                                 (drawing_id,)).fetchone(), "Drawing")
    return photo_response(row["preview"], row["preview_type"])


@router.delete("/journal/drawings/{drawing_id}", status_code=204)
def delete_drawing(drawing_id: int):
    """Delete a sketch (not a whiteboard page's board: delete the page instead)."""
    with db() as conn:
        row = fetch_drawing(conn, drawing_id)
        if row["board"]:
            raise HTTPException(409, "That's a whiteboard page's board. Delete the page instead.")
        conn.execute("DELETE FROM journal_drawings WHERE drawing_id = %s", (drawing_id,))
        refresh_page_text(conn, row["page_id"])
    return Response(status_code=204)
