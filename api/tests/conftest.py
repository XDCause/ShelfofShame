"""Shared test setup. Run the suite with .\\run_tests.ps1 from the project folder.

The tests run against a separate, freshly built database (hobby_inventory_test) and never
touch your real data. tamiya.com is replaced by a fake, so tests are fast and offline.
"""
import os
from pathlib import Path

import pytest

if not os.environ.get("POSTGRES_DB", "").endswith("_test"):
    pytest.exit("Refusing to run: POSTGRES_DB must be a *_test database (use run_tests.ps1).",
                returncode=2)

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, tamiya  # noqa: E402
from app.db import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    """Every test starts with the seeded lookup lists and nothing else."""
    with db() as conn:
        conn.execute("TRUNCATE stock_movements, wishlist, barcode_catalog, product_info, supplies, "
                     "model_paints, models, catalog_products, model_sessions, model_log, model_log_photos, colour_groups, "
                     "colour_group_members, mixes, mix_parts, price_guide, journal_pages, tags, page_tags, "
                     "journal_links, journal_images, journal_drawings, calendar_events, board_games, board_game_plays, gear, "
                     "volleyball_games, volleyball_teams, volleyball_videos, vg_achievements, vg_games, vg_other_games, "
                     "chess_games, chess_archives, books, reading_log, book_quotes, vg_friends, volleyball_coach, goals, site_checks, hikes, hike_photos, hike_gear, garden_spaces, garden_containers, garden_plantings, garden_logs, garden_photos, garden_tasks, garden_items, shooting_ranges, rifles, ammo, shooting_sessions, shooting_groups, shooting_shots, shooting_media, rifle_logs, dope_rows, trips, trip_places, travel_countries, vg_playtime, banners, auth_account, auth_recovery_codes, auth_sessions, auth_passkeys, auth_failures, todos "
                     "RESTART IDENTITY CASCADE")
        conn.execute("DELETE FROM settings WHERE key LIKE 'reading_goal_%%'")
        conn.execute("DELETE FROM garden_guides WHERE custom")
        conn.execute("UPDATE shooting_settings SET licence_expires = NULL, licence_note = NULL, club_shoots_needed = NULL, clean_every = 200")
        conn.execute("UPDATE travel_settings SET passport_expires = NULL")
        conn.execute("DELETE FROM packing_lists WHERE name NOT IN ('Essentials', 'Overseas', 'Beach', 'Cold weather', 'Camping', "
                     "'Road trip', 'Hiking trip', 'Shooting trip', 'Volleyball tournament')")
        conn.execute("UPDATE garden_settings SET climate = 'Subtropical', place_name = NULL, lat = NULL, lon = NULL")
        conn.execute("UPDATE chess_account SET username = NULL, profile = NULL, stats = NULL, last_sync_at = NULL, "
                     "last_error = NULL")
        conn.execute("UPDATE vg_sync SET profile = NULL, steam_id = NULL, persona_name = NULL, last_sync_at = NULL, "
                     "last_full_at = NULL, last_error = NULL, exo_profile = NULL, exo_players = NULL, "
                     "exo_synced_at = NULL, exo_error = NULL")
        # the seeded settings (db/init/15_settings.sql)
        conn.execute("UPDATE settings SET value = 'Hobbyrama' WHERE key = 'default_shop'")
        conn.execute("DELETE FROM settings WHERE key = 'your_name'")
        conn.execute("""INSERT INTO price_guide (label, title_contains, paint_type, size, price, sort_order)
                        VALUES ('Panel Line Accent', 'PANEL LINE ACCENT', NULL, NULL, 10.95, 1),
                               ('Acrylic paint, 10ml', NULL, 'Acrylic', '10ml', 3.95, 2)""")
        conn.execute("DELETE FROM brands WHERE name NOT IN ('Tamiya', 'Milliput', 'Microscale', 'Other')")
        conn.execute("DELETE FROM categories WHERE name LIKE 'Test %'")
        conn.execute("DELETE FROM storage_locations WHERE name LIKE 'Test %'")
    yield


# tests/test_robustness.py sets this: every outside site is "down" - each guarded call raises that module's own
# "couldn't reach it" error, as the real one does when the network fails - instead of failing the test.
SITES_DOWN = {"on": False}


@pytest.fixture(autouse=True)
def no_real_steam(monkeypatch):
    """Tests never call an outside site (Steam, shops, Open Library...) or use the real Steam key: a test that forgets
    to fake one fails."""
    import httpx

    from app import (bluesky, bookseries, bunnings, chess, goodgames, chesscom, exophase, frankfurter, hiking, openlibrary, openmeteo,
                     overpass,
                     reading, steam,
                     stedi, steamhunters, trumpeter, videogames, gameology, ucp, wikimedia)

    def refusing(down_error):
        def refuse(*_a, **_k):
            if SITES_DOWN["on"]:
                raise down_error("Couldn't reach it (the site is down, a test says).")
            raise AssertionError("A test tried to call a real outside site")
        return refuse
    connect_error = lambda msg: httpx.ConnectError(msg)     # noqa: E731 - trumpeter's _get lets httpx errors through
    monkeypatch.setattr(steam, "_get", refusing(steam.SteamError))
    monkeypatch.setattr(steam, "pause", lambda: None)
    monkeypatch.setattr(steamhunters, "_get", refusing(steamhunters.Unavailable))
    monkeypatch.setattr(steamhunters, "pause", lambda: None)
    monkeypatch.setattr(exophase, "_get", refusing(exophase.Unavailable))
    monkeypatch.setattr(steam, "find_app", refusing(steam.SteamError))            # Steam's store search (not via steam._get)
    monkeypatch.setattr(steam, "store_search", refusing(steam.SteamError))
    monkeypatch.setattr(chesscom, "_get", refusing(chesscom.ChessError))
    monkeypatch.setattr(chesscom, "pause", lambda: None)
    monkeypatch.setattr(openlibrary, "_get", refusing(openlibrary.BookError))
    monkeypatch.setattr(bookseries, "_wikidata", refusing(bookseries.SeriesError))
    monkeypatch.setattr(goodgames, "_call", refusing(ucp.ShopError))
    monkeypatch.setattr(bluesky, "_call", refusing(ucp.ShopError))
    monkeypatch.setattr(stedi, "_call", refusing(ucp.ShopError))
    monkeypatch.setattr(ucp, "PAUSE", 0)                  # the shops' product search (Good Games, Blue Sky)
    monkeypatch.setattr(ucp, "RETRY_WAIT", 0)
    monkeypatch.setattr(gameology, "_get", refusing(gameology.ShopError))
    monkeypatch.setattr(gameology, "photo", refusing(gameology.ShopError))
    monkeypatch.setattr(gameology, "PAUSE", 0)
    monkeypatch.setattr(openlibrary, "pause", lambda: None)
    monkeypatch.setattr(overpass, "_post", refusing(overpass.OverpassError))
    monkeypatch.setattr(overpass, "RETRY_WAITS", ())
    monkeypatch.setattr(wikimedia, "_get", refusing(wikimedia.CommonsError))
    monkeypatch.setattr(bunnings, "_get", refusing(bunnings.BunningsError))
    monkeypatch.setattr(bunnings, "photo", lambda image: (None, None))
    monkeypatch.setattr(bunnings, "PAUSE", 0)
    monkeypatch.setattr(openmeteo, "_get", refusing(openmeteo.WeatherError))
    openmeteo._cache.clear()
    monkeypatch.setattr(frankfurter, "_get", refusing(frankfurter.RatesError))
    frankfurter._cache.clear()
    monkeypatch.setattr(trumpeter, "_get", refusing(connect_error))
    monkeypatch.setattr(trumpeter, "PAUSE", 0)
    hiking.LOOKING.clear()
    auth.CHALLENGES.clear()
    reading.COVERS.update(running=False, done=0, total=0, found=0, error=None)
    chess.SYNC.update(running=False, done=0, total=0, message=None, error=None, finished_at=None)
    monkeypatch.setattr(exophase, "pause", lambda: None)
    videogames.SYNC.update(running=False, done=0, total=0, message=None, error=None, finished_at=None)


@pytest.fixture
def client():
    """A signed-in device (every route but signing in needs one): the account and a session made straight in the
    database. https://, as the app's cookie is only sent over https."""
    signed_in = TestClient(app, base_url="https://testserver")
    token = sign_in_directly()
    signed_in.cookies.set(auth.COOKIE, token)
    return signed_in


TEST_PASSWORD = "correct horse battery staple"
_TEST_HASH = auth.HASHER.hash(TEST_PASSWORD)      # once: Argon2 is slow on purpose


def sign_in_directly() -> str:
    import secrets
    token = secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute("INSERT INTO auth_account (account_id, password_hash) VALUES (1, %s) ON CONFLICT DO NOTHING", (_TEST_HASH,))
        conn.execute("INSERT INTO auth_sessions (token_hash, method, expires_at) VALUES (%s, 'password', now() + interval '1 day')",
                     (auth.sha256(token),))
    return token


@pytest.fixture
def anon():
    """A device that hasn't signed in."""
    return TestClient(app, base_url="https://testserver")


@pytest.fixture
def ids():
    """Ids of seeded lookup rows the tests use."""
    with db() as conn:
        one = lambda q: conn.execute(q).fetchone()["id"]  # noqa: E731
        return {
            "tamiya": one("SELECT brand_id AS id FROM brands WHERE name = 'Tamiya'"),
            "milliput": one("SELECT brand_id AS id FROM brands WHERE name = 'Milliput'"),
            "paint": one("SELECT category_id AS id FROM categories WHERE name = 'Paint'"),
            "glue": one("SELECT category_id AS id FROM categories WHERE name = 'Glue / Cement'"),
            "other_location": one("SELECT location_id AS id FROM storage_locations WHERE name = 'Other'"),
        }


@pytest.fixture
def make_supply(client, ids):
    """Create a supply through the API; keyword arguments override the defaults."""
    def make(**overrides):
        body = {"brand_id": ids["tamiya"], "product_code": "T81701", "name": "Acrylic XF1 Flat Black",
                "category_id": ids["paint"], "paint_type": "Acrylic", "finish": "Flat / Matt",
                "size": "10ml", "qty_on_hand": 1, "reorder_at": 0, "unit_price": "3.95"}
        body.update(overrides)
        r = client.post("/api/supplies", json=body)
        assert r.status_code == 201, r.text
        return r.json()
    return make


FAKE_PRODUCTS = {
    "81776": {"title": "ACRYLIC PAINT MINI XF-76 GRAY GREEN (IJN)",
              "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "81701": {"title": "ACRYLIC PAINT MINI XF-1 FLAT BLACK",
              "series": "Tamiya Color Acrylic Paint Mini", "description": "Contents: 10ml"},
    "87038": {"title": "TAMIYA EXTRA-THIN CEMENT (40ml)", "series": "Cement & Putty No.38",
              "description": None},
}

FIXTURES = Path(__file__).parent / "fixtures"
# The 1/48 M4A3E8 Sherman kit page, with its "Tamiya Colors required" list (trimmed copy).
SHERMAN = tamiya.parse((FIXTURES / "tamiya_kit_32595.html").read_text(encoding="utf-8"))
SHERMAN.pop("image_url")
FAKE_PRODUCTS["32595"] = SHERMAN


@pytest.fixture
def tamiya_catalogue(ids):
    """A few real Tamiya catalogue rows (titles as Tamiya writes them)."""
    rows = [
        ("81762", "ACRYLIC PAINT MINI XF-62 OLIVE DRAB", "Paints"),
        ("80362", "XF-62 OLIVE DRAB", "Paints"),                   # enamel: same code
        ("81362", "ACRYLIC PAINT XF-62 OLIVE DRAB", "Paints"),     # big jar: same code
        ("82128", "LP-28 OLIVE DRAB", "Paints"),                   # lacquer: same name
        ("85005", "TS-5 OLIVE DRAB", "Paints"),                    # spray: same name
        ("81702", "ACRYLIC PAINT MINI XF-2 FLAT WHITE", "Paints"),
        ("81701", "ACRYLIC PAINT MINI XF-1 FLAT BLACK", "Paints"),
        ("82103", "LP-3 FLAT BLACK", "Paints"),
        ("81507", "ACRYLIC PAINT MINI X-7 RED", "Paints"),
        ("81520", "ACRYLIC PAINT MINI X-20A THINNER (10ml)", "Paints"),
        ("87131", "PANEL LINE ACCENT COLOR (BLACK)", "Finishing Materials"),
        ("X62", "TAMIYA COLOR XF-62 OLIVE DRAB", "Paints"),        # a generic page: ignored
    ]
    with db() as conn:
        for item, title, genre in rows:
            conn.execute("INSERT INTO catalog_products (brand_id, product_code, item, title, genre) "
                         "VALUES (%s, %s, %s, %s, %s)",
                         (ids["tamiya"], tamiya.product_code(item), item, title, genre))
    return rows


@pytest.fixture
def fake_tamiya(monkeypatch):
    """Stand-in for tamiya.fetch. Returns the list of item numbers it was asked for."""
    calls = []

    def fetch(item):
        calls.append(item)
        if item not in FAKE_PRODUCTS:
            raise tamiya.NotFound(f"Tamiya has no product page for item {item}.")
        return {"kit_paints": [], **FAKE_PRODUCTS[item],
                "source_url": f"https://www.tamiya.com/english/products/{item}/index.html",
                "image": b"\xff\xd8fake-jpeg", "image_type": "image/jpeg"}

    monkeypatch.setattr(tamiya, "fetch", fetch)
    return calls
