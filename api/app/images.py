"""Photos sent to the API (product photos, build log photos): the same rules for all of them.

The browser shrinks a photo to <= 1000 px JPEG before sending it, so they're small.
"""
from fastapi import HTTPException, Request, Response

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
    """A stored photo. URLs carry ?v=<when it changed>, so the browser can keep it for a day."""
    if image is None:
        raise HTTPException(404, "No photo.")
    return Response(content=bytes(image), media_type=image_type or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})
