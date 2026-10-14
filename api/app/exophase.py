"""Which achievements come with a DLC, from Exophase's game pages (www.exophase.com).

Steam lists a game's DLC achievements together with the main game's, with nothing to say which is
which. Exophase's achievement pages put each DLC in its own section:

    <ul class="... achievement ...">  <li class="award"> ... .award-title a = name ...   (main game)
    <h3 class="dlc-add-on"><span>Borderlands 2: Captain Scarlett ... Achievements</span></h3>
    <ul class="... achievement ...">  ...                                                  (that DLC)

Finding the page: Exophase's own public API (api.exophase.com/public/archive/games?q=<name>, the
one its site uses; robots.txt only blocks /search) lists games by name, and the page is only used
if it links to the same Steam app (store.steampowered.com/app/<id>), so a namesake can't be picked.
Achievements are matched to Steam's by name (ignoring case and punctuation).

Exophase heads free content updates ("Update #1", "Commander Mode") the same way as paid DLC, so a
section only counts as DLC if its name matches one of the game's real DLCs (SteamHunters' list);
the rest belong to the main game - they count towards its 100% like any other achievement.

Gentle: only started games SteamHunters says have DLC, one request every two seconds, saved in the
database and read again only when a game's achievements change or on a full sync. No published
API terms - personal use only (see BEFORE_GOING_PUBLIC.md).
"""
import re
import time
import unicodedata

import httpx
from bs4 import BeautifulSoup

SEARCH = "https://api.exophase.com/public/archive/games"
HEADERS = {"User-Agent": "Off the Clock (personal hobby tracker; one user, gentle)"}
TIMEOUT = 20
PAUSE = 2.0
TRIES = 3          # pages to check (best name matches first) before giving up on a game


class Unavailable(Exception):
    """Exophase can't be reached right now: try again next sync."""


def _get(url: str, params: dict | None = None):
    """One request; if it times out, one more try 5 s later."""
    for attempt in (1, 2):
        try:
            return httpx.get(url, params=params, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
        except httpx.TimeoutException:
            if attempt == 1:
                time.sleep(5)
                continue
            raise Unavailable("Couldn't reach Exophase (it timed out twice).") from None
        except httpx.HTTPError as e:
            raise Unavailable(f"Couldn't reach Exophase ({e.__class__.__name__}).") from None


def pause():
    time.sleep(PAUSE)


def key(text: str) -> str:
    """For matching names: "First One's Free" == "first ones free"; full-width and accented letters folded."""
    text = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", re.sub(r"[™®©]", "", text or "")))
    return re.sub(r"[^0-9a-z]+", "", "".join(c for c in text if not unicodedata.combining(c)).casefold())


def search_name(name: str) -> str:
    """The game's name as Exophase's search wants it: no ™ / ® / ©, single spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[™®©]", "", name)).strip()


def candidates(name: str, total: int | None) -> list[str]:
    """Exophase's Steam pages for a game name, best first: the same name, then the same number of
    achievements, then the rest."""
    r = _get(SEARCH, {"q": search_name(name), "sort": "added"})
    if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
        raise Unavailable(f"Exophase didn't answer (HTTP {r.status_code}).")
    games = (r.json().get("games") or {}).get("list") or []
    steam = [g for g in games if g.get("environment_slug") == "steam" and g.get("endpoint_awards")]
    wanted = key(search_name(name))   # without the ™ (which would fold to "TM")
    steam.sort(key=lambda g: (key(g.get("title")) != wanted, g.get("total_awards") != total))
    return [g["endpoint_awards"] for g in steam]


def links_to(html: str, app_id: int) -> bool:
    """Whether the page is about this Steam app (it links to the store page or the stats page)."""
    return re.search(rf"(store\.steampowered\.com/app|steamcommunity\.com/stats)/{app_id}(?!\d)", html) is not None


def dlc_name(heading: str, game: str) -> str:
    """"Borderlands 2: Captain Scarlett and her Pirate's Booty Achievements" -> "Captain Scarlett and
    her Pirate's Booty" (the game's name and the word Achievements add nothing in the game's panel).
    Also "Far Cry® 5 - Lost On Mars" for "Far Cry 5", "Just Cause™ 3 DLC: Mech Land Assault",
    "Fallout 4 Far Harbor", and "The Binding of Isaac: Afterbirth" for "...: Rebirth" (the series)."""
    name = re.sub(r"\s+Achievements$", "", heading.strip(), flags=re.I)
    g = key(game)
    rest = None
    for m in re.finditer(r"\s*:\s*|\s+[-–—]\s+", name):     # the longest start that's the game (or its series)
        k = key(name[:m.start()])
        if k and (k in (g, g + "dlc") or (len(k) >= 6 and g.startswith(k))):
            rest = name[m.end():]
    if rest is None:                                      # "Fallout 4 Far Harbor": the game's name, then a space
        for m in re.finditer(r"\s+", name):
            if key(name[:m.start()]) == g:
                rest = name[m.end():]
                break
    return rest.strip() if rest and rest.strip() else name


def is_dlc(section: str, game: str, dlcs: list[str]) -> bool:
    """Whether a page section (already without the game's name) is one of the game's DLCs, e.g.
    "Spaced Out!" for "Oxygen Not Included - Spaced Out!"; "Update #1" isn't."""
    s = key(section)
    if not s:
        return False
    for d in dlcs:
        k = key(dlc_name(d, game))
        if s == k or (min(len(s), len(k)) >= 5 and (s in k or k in s)):
            return True
    return False


def parse(html: str, game: str) -> list[tuple[str | None, str]]:
    """Every achievement on the page as (DLC name or None for the main game, achievement name)."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for ul in soup.select("ul.achievement"):
        heading = ul.find_previous("h3", class_="dlc-add-on")
        dlc = dlc_name(heading.get_text(" ", strip=True), game) if heading else None
        for li in ul.find_all("li", class_="award", recursive=False):
            title = li.select_one(".award-title")
            if title:
                found.append((dlc, title.get_text(" ", strip=True)))
    return found


def dlc_of(app_id: int, name: str, total: int | None, dlcs: list[str]) -> tuple[str, dict[str, str | None]]:
    """(the page used, {name key: DLC name or None}) for a Steam game whose DLCs are called `dlcs`;
    ("", {}) if Exophase has no page for it. Raises Unavailable if Exophase can't be reached."""
    for url in candidates(name, total)[:TRIES]:
        pause()
        r = _get(url)
        if r.status_code == 200 and links_to(r.text, app_id):
            return url, {key(n): (section if section and is_dlc(section, name, dlcs) else None)
                         for section, n in parse(r.text, name)}
        if r.status_code not in (200, 404):
            raise Unavailable(f"Exophase didn't answer (HTTP {r.status_code}).")
    return "", {}
