"""Photos sent to the API (products, build log, board games, gear): the same rules for all of them.

The browser shrinks a photo to <= 1000 px JPEG before sending it, so they're small.
"""
from fastapi import HTTPException, Request, Response

from .db import db, found

PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


async def read_photo(request: Request) -> tuple[bytes, str]:
    """The uploaded image (the request body) and its type, or a clear error."""
    image_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if image_type not in PHOTO_TYPES:
        raise HTTPException(415, "Photos must be JPEG, PNG, WebP or GIF.")
    image = await request.body()
    if not image:
        raise HTTPException(422, "No photo was sent.")
    if len(image) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "That photo is over 5 MB.")
    return image, image_type


def photo_response(image, image_type: str | None) -> Response:
    """A stored photo. Its URL changes when the photo does (?v=<when>, or a new id for journal
    photos), so the browser can keep it for a year without asking again."""
    if image is None:
        raise HTTPException(404, "No photo.")
    return Response(content=bytes(image), media_type=image_type or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable",
                             "X-Content-Type-Options": "nosniff"})


def fetched_photo(response) -> tuple[bytes | None, str | None]:
    """A photo downloaded from a maker's or shop's site, if it's a usable one: a JPEG, PNG, WebP or
    GIF (not SVG, which can carry script) of at most 5 MB. Otherwise (None, None)."""
    image_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if response.status_code != 200 or image_type not in PHOTO_TYPES or len(response.content) > MAX_PHOTO_BYTES:
        return None, None
    return response.content, image_type


def add_photo_routes(router, path: str, table: str, id_col: str, what: str):
    """GET / PUT / DELETE <path>/{id}/photo for a table that keeps its own photo in
    photo / photo_type / photo_updated columns (board games, gear)."""
    @router.get(f"{path}/{{row_id}}/photo", name=f"{table}_photo")
    def get_photo(row_id: int):
        with db() as conn:
            row = found(conn.execute(f"SELECT photo, photo_type FROM {table} WHERE {id_col} = %s",
                                     (row_id,)).fetchone(), what)
        return photo_response(row["photo"], row["photo_type"])

    @router.put(f"{path}/{{row_id}}/photo", name=f"{table}_photo_put")
    async def put_photo(row_id: int, request: Request):
        image, image_type = await read_photo(request)
        with db() as conn:
            found(conn.execute(f"UPDATE {table} SET photo = %s, photo_type = %s, photo_updated = now() "
                               f"WHERE {id_col} = %s RETURNING {id_col}", (image, image_type, row_id)).fetchone(), what)
        return Response(status_code=204)

    @router.delete(f"{path}/{{row_id}}/photo", name=f"{table}_photo_delete")
    def delete_photo(row_id: int):
        with db() as conn:
            found(conn.execute(f"UPDATE {table} SET photo = NULL, photo_type = NULL, photo_updated = now() "
                               f"WHERE {id_col} = %s RETURNING {id_col}", (row_id,)).fetchone(), what)
        return Response(status_code=204)
