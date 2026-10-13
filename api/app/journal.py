"""The journal: Notion-style pages (part of the core, not a hobby module).

A page's body is BlockNote's JSON: a list of blocks (paragraph, heading, checklist item, image...)
each with inline `content` (text, links, and our own `mention` items) and nested `children`.
The API doesn't need to understand the blocks. On every save it works out two things from them:
    text   all the words, for search
    links  what the page @mentions: {"type": "mention", "props": {"kind": "model", "ref": "3",
           "label": "Sherman"}} -> journal_links (model 3), so the model can list pages about it
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .db import db, found, insert_row, update_row
from .images import photo_response, read_photo

router = APIRouter(prefix="/api", tags=["journal"])

KINDS = ("model", "supply", "page")


class PageIn(BaseModel):
    title: str = ""
    icon: str | None = Field(None, max_length=16)
    entry_date: date | None = None
    content: list = []
    pinned: bool = False
    tags: list[str] = []


class PagePatch(BaseModel):
    title: str | None = None
    icon: str | None = Field(None, max_length=16)
    entry_date: date | None = None
    content: list | None = None
    pinned: bool | None = None
    tags: list[str] | None = None


# ---------------------------------------------------------------------------
# Reading the blocks
# ---------------------------------------------------------------------------
def _inline(content) -> str:
    """The words in a block's inline content: text, links, mentions and table cells."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_inline(item) for item in content)
    if isinstance(content, dict):
        if content.get("type") == "mention":
            return "@" + str(content.get("props", {}).get("label", ""))
        if content.get("type") == "tableContent":
            return " ".join(_inline(cell) for row in content.get("rows", []) for cell in row.get("cells", []))
        if isinstance(content.get("text"), str):
            return content["text"]
        return _inline(content.get("content", ""))     # a link or a table cell
    return ""


def plain_text(blocks) -> str:
    """Every word in the blocks, one block per line (nested blocks included)."""
    lines = []
    for block in blocks or []:
        if not isinstance(block, dict):
            continue
        line = _inline(block.get("content")).strip()
        if line:
            lines.append(line)
        nested = plain_text(block.get("children"))
        if nested:
            lines.append(nested)
    return "\n".join(lines)


def mentions(node) -> set[tuple[str, int]]:
    """Every (kind, id) the blocks @mention."""
    found_ = set()

    def walk(n):
        if isinstance(n, list):
            for item in n:
                walk(item)
        elif isinstance(n, dict):
            if n.get("type") == "mention":
                props = n.get("props", {})
                kind, ref = props.get("kind"), str(props.get("ref", ""))
                if kind in KINDS and ref.isdigit():
                    found_.add((kind, int(ref)))
            for value in n.values():
                if isinstance(value, (list, dict)):
                    walk(value)

    walk(node)
    return found_


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------
def save_tags(conn, page_id: int, names: list[str]):
    clean = sorted({n.strip() for n in names if n and n.strip()}, key=str.lower)
    conn.execute("DELETE FROM page_tags WHERE page_id = %s", (page_id,))
    for name in clean:
        conn.execute("INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
        conn.execute("INSERT INTO page_tags (page_id, tag_id) SELECT %s, tag_id FROM tags WHERE name = %s",
                     (page_id, name))
    # A tag no page uses any more is forgotten.
    conn.execute("DELETE FROM tags t WHERE NOT EXISTS (SELECT 1 FROM page_tags pt WHERE pt.tag_id = t.tag_id)")


def save_links(conn, page_id: int, content: list):
    conn.execute("DELETE FROM journal_links WHERE page_id = %s", (page_id,))
    for kind, target in sorted(mentions(content)):
        if kind == "page" and target == page_id:
            continue                                    # a page mentioning itself
        conn.execute("INSERT INTO journal_links (page_id, target_kind, target_id) VALUES (%s, %s, %s)",
                     (page_id, kind, target))


PAGE_LIST = """
SELECT p.page_id, p.title, p.icon, p.entry_date, p.pinned, p.created_at, p.updated_at,
       left(p.text, 200) AS snippet,
       COALESCE((SELECT array_agg(t.name ORDER BY lower(t.name)) FROM page_tags pt JOIN tags t USING (tag_id)
                 WHERE pt.page_id = p.page_id), '{}') AS tags
FROM journal_pages p
"""

# What a link points at, by name (deleted things show as gone).
TARGET_NAME = """
CASE l.target_kind
    WHEN 'model'  THEN (SELECT name FROM models WHERE model_id = l.target_id)
    WHEN 'supply' THEN (SELECT name FROM supplies WHERE supply_id = l.target_id)
    WHEN 'page'   THEN (SELECT COALESCE(NULLIF(title, ''), 'Untitled') FROM journal_pages WHERE page_id = l.target_id)
END"""


def fetch_page(conn, page_id: int) -> dict:
    page = found(conn.execute(
        "SELECT p.*, COALESCE((SELECT array_agg(t.name ORDER BY lower(t.name)) FROM page_tags pt "
        "JOIN tags t USING (tag_id) WHERE pt.page_id = p.page_id), '{}') AS tags "
        "FROM journal_pages p WHERE p.page_id = %s", (page_id,)).fetchone(), "Journal page")
    page["links"] = conn.execute(
        f"SELECT l.target_kind AS kind, l.target_id AS id, {TARGET_NAME} AS name FROM journal_links l "
        "WHERE l.page_id = %s ORDER BY 1, 3", (page_id,)).fetchall()
    # Pages that mention this one.
    page["mentioned_in"] = conn.execute(
        PAGE_LIST + " JOIN journal_links l ON l.page_id = p.page_id "
        "WHERE l.target_kind = 'page' AND l.target_id = %s ORDER BY p.entry_date DESC", (page_id,)).fetchall()
    return page


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@router.get("/journal")
def list_pages(q: str | None = None, tag: str | None = None,
               mention: str | None = Query(None, pattern=r"^(model|supply|page):\d+$"),
               limit: int = Query(200, ge=1, le=1000)):
    """Newest first (pinned ones on top). q searches titles and text; tag filters by a tag;
    mention=model:3 lists the pages that @mention model 3."""
    where, params = [], []
    if q and q.strip():
        for word in q.split():
            where.append("(p.title ILIKE %s OR p.text ILIKE %s)")
            params += [f"%{word}%", f"%{word}%"]
    if tag:
        where.append("EXISTS (SELECT 1 FROM page_tags pt JOIN tags t USING (tag_id) "
                     "WHERE pt.page_id = p.page_id AND t.name = %s)")
        params.append(tag)
    if mention:
        kind, target = mention.split(":")
        where.append("EXISTS (SELECT 1 FROM journal_links l WHERE l.page_id = p.page_id "
                     "AND l.target_kind = %s AND l.target_id = %s)")
        params += [kind, int(target)]
    sql = PAGE_LIST + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY p.pinned DESC, p.entry_date DESC, p.page_id DESC LIMIT %s"
    with db() as conn:
        return conn.execute(sql, (*params, limit)).fetchall()


@router.post("/journal", status_code=201)
def add_page(body: PageIn):
    data = body.model_dump(exclude={"tags"})
    if data["entry_date"] is None:
        data.pop("entry_date")                       # the database's default: today
    data["text"] = plain_text(body.content)
    data["content"] = Jsonb(body.content)
    with db() as conn:
        page_id = insert_row(conn, "journal_pages", data, "page_id")
        save_tags(conn, page_id, body.tags)
        save_links(conn, page_id, body.content)
        return fetch_page(conn, page_id)


@router.get("/journal/tags")
def list_tags():
    """Every tag, with how many pages use it."""
    with db() as conn:
        return conn.execute("SELECT t.name, count(*) AS pages FROM tags t JOIN page_tags pt USING (tag_id) "
                            "GROUP BY t.name ORDER BY lower(t.name)").fetchall()


@router.get("/journal/mentionable")
def mentionable(q: str = ""):
    """What can be @mentioned, matching q: models, supplies and pages (up to 8 of each)."""
    like = f"%{q.strip()}%"
    with db() as conn:
        rows = conn.execute("""
            (SELECT 'model' AS kind, model_id AS id, name AS label, 'Model' AS what FROM models
             WHERE name ILIKE %(q)s ORDER BY name LIMIT 8)
            UNION ALL
            (SELECT 'supply', supply_id, name, 'Supply' FROM supplies
             WHERE name ILIKE %(q)s OR product_code ILIKE %(q)s ORDER BY name LIMIT 8)
            UNION ALL
            (SELECT 'page', page_id, COALESCE(NULLIF(title, ''), 'Untitled'), 'Journal page' FROM journal_pages
             WHERE title ILIKE %(q)s ORDER BY entry_date DESC LIMIT 8)""", {"q": like}).fetchall()
    return rows


@router.get("/journal/{page_id}")
def get_page(page_id: int):
    with db() as conn:
        return fetch_page(conn, page_id)


@router.patch("/journal/{page_id}")
def update_page(page_id: int, body: PagePatch):
    data = body.model_dump(exclude_unset=True)
    tags = data.pop("tags", None)
    if "entry_date" in data and data["entry_date"] is None:
        raise HTTPException(422, "A page needs a date.")
    if data.get("content") is not None:
        data["text"] = plain_text(data["content"])
    with db() as conn:
        fetch_page(conn, page_id)                       # 404 if it doesn't exist
        if "content" in data:
            save_links(conn, page_id, data["content"])
            data["content"] = Jsonb(data["content"])
        update_row(conn, "journal_pages", "page_id", page_id, data)
        if tags is not None:
            save_tags(conn, page_id, tags)
        return fetch_page(conn, page_id)


@router.delete("/journal/{page_id}", status_code=204)
def delete_page(page_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM journal_pages WHERE page_id = %s RETURNING page_id", (page_id,)).fetchone(),
              "Journal page")
        conn.execute("DELETE FROM journal_links WHERE target_kind = 'page' AND target_id = %s", (page_id,))
        conn.execute("DELETE FROM tags t WHERE NOT EXISTS (SELECT 1 FROM page_tags pt WHERE pt.tag_id = t.tag_id)")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Photos in pages
# ---------------------------------------------------------------------------
@router.post("/journal/images", status_code=201)
async def add_image(request: Request, page_id: int | None = None):
    """A photo dropped into a page (the image is the request body). Returns its address."""
    image, image_type = await read_photo(request)
    with db() as conn:
        image_id = insert_row(conn, "journal_images",
                              {"page_id": page_id, "image": image, "image_type": image_type}, "image_id")
    return {"image_id": image_id, "url": f"/api/journal/images/{image_id}"}


@router.get("/journal/images/{image_id}")
def get_image(image_id: int):
    with db() as conn:
        row = found(conn.execute("SELECT image, image_type FROM journal_images WHERE image_id = %s",
                                 (image_id,)).fetchone(), "Image")
    return photo_response(row["image"], row["image_type"])
