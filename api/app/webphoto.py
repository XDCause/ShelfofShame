"""A photo from a web address, for anywhere a photo can be added (gear, board games, kits...).

The browser can't download a picture from another site itself (other sites don't allow it), so it
sends the picture's address here and gets the picture back; it then shrinks and saves it like any
photo you pick from your computer. Nothing is stored here.

Fetching an address someone typed is a classic way in to a home network ("server-side request
forgery"), so only public web addresses are fetched: http(s) on the usual ports, a host that
resolves to public internet addresses only (never this PC, the Docker network or the home Wi-Fi),
each redirect checked the same way, at most 5 MB, and the bytes must really be a JPEG / PNG / WebP /
GIF picture (not SVG, which can carry script).
"""
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .images import MAX_PHOTO_BYTES

router = APIRouter(prefix="/api", tags=["photos"])

HEADERS = {"User-Agent": "Mozilla/5.0 (personal hobby tracker 'Off the Clock'; fetching one picture a person chose)",
           "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif;q=0.9,*/*;q=0.5"}
TIMEOUT = 15
REDIRECTS = 4


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


def kind_of(head: bytes) -> str | None:
    """The picture's type from its first bytes (a server's content-type can't be trusted)."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_address(url: str):
    """Refuse anything but a public http(s) address (see the module docstring)."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(422, "That isn't a web address (it should start with https://).")
    if parts.port not in (None, 80, 443):
        raise HTTPException(422, "Only ordinary web addresses can be used.")
    try:
        found = {a[4][0] for a in socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError):
        raise HTTPException(422, f"Couldn't find the site {parts.hostname}.") from None
    if not found or not all(ipaddress.ip_address(a.split("%")[0]).is_global for a in found):
        raise HTTPException(422, "Only public web addresses can be used (not this computer or your home network).")


def fetch(url: str) -> tuple[bytes, str]:
    """The picture at a public address, following up to REDIRECTS redirects (each one checked)."""
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=False) as client:
        for _ in range(REDIRECTS + 1):
            check_address(url)
            try:
                with client.stream("GET", url) as r:
                    if r.is_redirect and r.headers.get("location"):
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code != 200:
                        raise HTTPException(422, f"The site said no (HTTP {r.status_code}). Try saving the picture and "
                                                 "pasting it instead.")
                    body = bytearray()
                    for chunk in r.iter_bytes():
                        body += chunk
                        if len(body) > MAX_PHOTO_BYTES:
                            raise HTTPException(413, "That picture is over 5 MB.")
            except httpx.HTTPError as e:
                raise HTTPException(422, f"Couldn't download it ({e.__class__.__name__}).") from None
            image_type = kind_of(bytes(body[:16]))
            if not image_type:
                raise HTTPException(422, "That address isn't a picture (use the picture's own address: right-click it, "
                                         "Copy image address).")
            return bytes(body), image_type
    raise HTTPException(422, "Too many redirects.")


@router.post("/photo-from-url")
def photo_from_url(body: UrlIn):
    image, image_type = fetch(body.url.strip())
    return Response(content=image, media_type=image_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
