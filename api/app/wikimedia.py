"""Wikimedia Commons (https://commons.wikimedia.org/w/api.php) and Wikidata: free-licensed photos. No key;
they ask apps to say who they are (User-Agent). Used by Hiking for photos people took near a hike's
track, and a landmark's own photo (its OpenStreetMap wikimedia_commons or wikidata tag).

    near(lat, lon, radius)   photos taken within `radius` m (at most 10 km) -> [{title, lat, lon}]
    images(titles)           each photo's thumbnail, page, author and licence (50 per request)
    wikidata_images(ids)     Wikidata items' main photo (P18) -> {"Q123": "File:..."}

Thumbnails are shown straight from Wikimedia (they allow it); the author and licence are shown with
each one, as the licences require.
"""
import re

import httpx

from .openlibrary import HEADERS

COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
TIMEOUT = 20


class CommonsError(Exception):
    """Wikimedia couldn't be asked; the message says why."""


def _get(url: str, params: dict) -> dict:
    try:
        r = httpx.get(url, params={**params, "format": "json", "formatversion": "2"}, headers=HEADERS, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise CommonsError(f"Couldn't reach Wikimedia ({e.__class__.__name__}).") from None
    if r.status_code != 200:
        raise CommonsError(f"Wikimedia didn't answer (HTTP {r.status_code}).")
    return r.json()


def near(lat: float, lon: float, radius: int = 10000, limit: int = 100) -> list[dict]:
    data = _get(COMMONS, {"action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}",
                          "gsradius": max(10, min(10000, int(radius))), "gsnamespace": 6, "gslimit": min(limit, 500)})
    return [{"title": g["title"], "lat": g["lat"], "lon": g["lon"]} for g in data.get("query", {}).get("geosearch", [])]


def _plain(html: str | None) -> str | None:
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()
    return text[:200] or None


def images(titles: list[str], width: int = 480) -> dict[str, dict]:
    """{title: {thumb, page, author, licence}} for the titles that are photos."""
    out = {}
    for i in range(0, len(titles), 50):
        data = _get(COMMONS, {"action": "query", "titles": "|".join(titles[i:i + 50]), "prop": "imageinfo",
                              "iiprop": "url|extmetadata|mime", "iiurlwidth": width,
                              "iiextmetadatafilter": "Artist|LicenseShortName"})
        for page in data.get("query", {}).get("pages", []):
            info = (page.get("imageinfo") or [None])[0]
            if not info or not str(info.get("mime", "")).startswith("image/") or not info.get("thumburl"):
                continue
            meta = info.get("extmetadata") or {}
            out[page["title"]] = {
                "thumb": info["thumburl"], "page": info.get("descriptionurl"),
                "author": _plain((meta.get("Artist") or {}).get("value")),
                "licence": _plain((meta.get("LicenseShortName") or {}).get("value")),
            }
    return out


def wikidata_images(ids: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(ids), 50):
        data = _get(WIKIDATA, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "claims"})
        for qid, entity in (data.get("entities") or {}).items():
            for claim in (entity.get("claims") or {}).get("P18", [])[:1]:
                name = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if isinstance(name, str) and name:
                    out[qid] = f"File:{name}"
    return out
