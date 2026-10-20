"""Page banners: the picture at the top of Home, the journal, the calendar and each hobby.

A banner without a photo of yours shows a drawn landscape (the web app draws it), so nothing here is needed
until you add one. A row is made the first time an area gets a photo.
"""
from fastapi import APIRouter, Path, Request, Response
from pydantic import BaseModel, Field

from .db import db, found
from .images import add_photo_routes, read_photo

router = APIRouter(prefix="/api", tags=["banners"])

AREA = r"^[a-z]{2,30}$"
SELECT = """SELECT banner_id, area, focus_y,
       CASE WHEN photo IS NOT NULL THEN '/api/banners/' || banner_id || '/photo?v='
                 || (extract(epoch FROM photo_updated) * 1000)::bigint END AS photo_url
FROM banners"""


@router.get("/banners")
def list_banners():
    """Every area with a picture of yours: {area: {banner_id, photo_url, focus_y}}."""
    with db() as conn:
        rows = conn.execute(SELECT + " WHERE photo IS NOT NULL ORDER BY area").fetchall()
    return {r["area"]: r for r in rows}


@router.put("/banners/area/{area}/photo")
async def set_banner(request: Request, area: str = Path(pattern=AREA)):
    """A picture for an area (made on first use), as the request body like any photo."""
    image, image_type = await read_photo(request)
    with db() as conn:
        return conn.execute(
            "INSERT INTO banners (area, photo, photo_type, photo_updated) VALUES (%s, %s, %s, now()) "
            "ON CONFLICT (area) DO UPDATE SET photo = EXCLUDED.photo, photo_type = EXCLUDED.photo_type, "
            "photo_updated = now() RETURNING banner_id", (area, image, image_type)).fetchone()


class BannerPatch(BaseModel):
    focus_y: int = Field(ge=0, le=100)


@router.patch("/banners/area/{area}")
def move_banner(body: BannerPatch, area: str = Path(pattern=AREA)):
    """Where the picture sits in the banner (0 = its top shows, 100 = its bottom)."""
    with db() as conn:
        found(conn.execute("UPDATE banners SET focus_y = %s WHERE area = %s RETURNING banner_id",
                           (body.focus_y, area)).fetchone(), "Banner")
        return conn.execute(SELECT + " WHERE area = %s", (area,)).fetchone()


@router.delete("/banners/area/{area}/photo")
def remove_banner(area: str = Path(pattern=AREA)):
    """Back to the drawn landscape."""
    with db() as conn:
        conn.execute("DELETE FROM banners WHERE area = %s", (area,))
    return Response(status_code=204)


# GET /banners/{id}/photo serves the picture (its URL changes with it, so it's cached for a year).
add_photo_routes(router, "/banners", "banners", "banner_id", "Banner")
