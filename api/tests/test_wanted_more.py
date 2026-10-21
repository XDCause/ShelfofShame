"""More for the wishlist (89_wishlist_more.sql, api/app/wanted_more.py, linkpeek.py): what it's for, target prices and
their history, saving up, shop checks, ticking anything bought (+ undo), the bought history, adding from a link."""
from datetime import date

from app import bluesky, goodgames, linkpeek

REAL_GET = linkpeek._get          # (conftest swaps it for a stand-in in every test; the redirect test needs the real one)

TODAY = date.today().isoformat()


def kit(client, name="1/700 Yamato", price=54):
    return client.post("/api/models", json={"name": name, "status": "Wanted", "price_paid": price}).json()


def test_extras_cover_every_kind_with_how_long_its_waited(client, make_supply, ids):
    k = kit(client)
    w = client.post("/api/wishlist", json={"name": "XF-62", "category_id": ids["paint"], "est_price": "6.50"}).json()
    g = client.post("/api/gear", json={"name": "Pads", "hobby": "volleyball", "condition": "Wanted"}).json()
    out = client.get("/api/wanted/extras").json()
    assert {f"model:{k['model_id']}", f"wish:{w['wish_id']}", f"gear:{g['gear_id']}"} <= set(out)
    assert out[f"model:{k['model_id']}"]["hobby"] == "models" and out[f"gear:{g['gear_id']}"]["hobby"] == "volleyball"
    assert out[f"model:{k['model_id']}"]["days"] == 0 and out[f"wish:{w['wish_id']}"]["price"] == 6.5


def test_for_target_price_and_price_history(client):
    k = kit(client)
    sherman = client.post("/api/models", json={"name": "Sherman"}).json()
    got = client.put(f"/api/wanted/model/{k['model_id']}", json={"for_model_id": sherman["model_id"], "target_price": "45"}).json()
    assert got["for_model"] == "Sherman" and got["target_price"] == 45 and not got["below_target"]    # $54 now
    client.post(f"/api/wanted/model/{k['model_id']}/prices", json={"price": "49.95", "source": "Hobbyrama"})
    after = client.post(f"/api/wanted/model/{k['model_id']}/prices", json={"price": "44"}).json()
    assert after["below_target"] and after["last_price"] == 44 and after["lowest_price"] == 44
    assert [p["price"] for p in client.get(f"/api/wanted/model/{k['model_id']}/prices").json()] == [49.95, 44]
    assert client.put(f"/api/wanted/model/{k['model_id']}", json={"for_goal_id": 99999}).status_code == 404
    assert client.put("/api/wanted/model/99999", json={}).status_code == 404


def test_saving_up_never_goes_below_nothing(client):
    k = kit(client)
    assert client.post(f"/api/wanted/model/{k['model_id']}/save", json={"amount": "20"}).json()["saved"] == 20
    assert client.post(f"/api/wanted/model/{k['model_id']}/save", json={"amount": "-50"}).json()["saved"] == 0


def test_got_it_makes_each_kind_yours_and_remembers_it(client, ids):
    k = kit(client)
    got = client.post(f"/api/wanted/model/{k['model_id']}/got", json={"paid": "50", "shop": "Hobbyrama"}).json()
    assert got["paid"] == "50.00" or got["paid"] == 50
    m = client.get(f"/api/models/{k['model_id']}").json()
    assert m["status"] == "In stash" and m["purchase_date"] == TODAY
    assert client.post(f"/api/wanted/model/{k['model_id']}/got").status_code == 409            # not wanted any more
    w = client.post("/api/wishlist", json={"name": "XF-62", "category_id": ids["paint"], "est_price": "6.50"}).json()
    client.post(f"/api/wanted/wish/{w['wish_id']}/got")
    hist = client.get("/api/wanted/history").json()
    assert [h["name"] for h in hist] == ["XF-62", "1/700 Yamato"] and hist[1]["paid"] == 50 and hist[1]["expected"] == 54
    assert any(s["name"] == "XF-62" for s in client.get("/api/supplies").json())
    client.post(f"/api/wanted/model/{k['model_id']}/ungot")                                     # a mistaken tick
    assert client.get(f"/api/models/{k['model_id']}").json()["status"] == "Wanted"
    assert [h["name"] for h in client.get("/api/wanted/history").json()] == ["XF-62"]


def test_the_wishlists_own_buy_is_remembered_too(client, ids):
    w = client.post("/api/wishlist", json={"name": "XF-1", "category_id": ids["paint"], "est_price": "3.95"}).json()
    client.post(f"/api/wishlist/{w['wish_id']}/buy", json={})
    assert client.get("/api/wanted/history").json()[0]["name"] == "XF-1"


def test_checking_a_shop_for_price_and_stock(client, monkeypatch):
    g = client.post("/api/gear", json={"name": "Wade shoes", "hobby": "volleyball", "condition": "Wanted"}).json()
    assert client.post(f"/api/wanted/gear/{g['gear_id']}/check").status_code == 409            # not from a shop
    from app.db import db
    with db() as conn:
        conn.execute("UPDATE gear SET shop_id = '123', shop_name = 'Blue Sky Athletics' WHERE gear_id = %s", (g["gear_id"],))
    monkeypatch.setattr(bluesky, "get", lambda pid: {"price": 199.95, "available": False})
    out = client.post(f"/api/wanted/gear/{g['gear_id']}/check").json()
    assert out["in_stock"] is False and out["last_price"] == 199.95 and out["last_source"] == "Blue Sky Athletics"
    game = client.post("/api/board-games", json={"name": "Brass: Birmingham", "status": "Wanted"}).json()
    with db() as conn:
        conn.execute("UPDATE board_games SET shop_handle = 'brass' WHERE game_id = %s", (game["game_id"],))
    monkeypatch.setattr(goodgames, "board_games", lambda q, limit=8: [{"handle": "brass", "price": 89.95, "available": True}])
    assert client.post(f"/api/wanted/game/{game['game_id']}/check").json()["in_stock"] is True


def test_reading_a_product_page(client, monkeypatch):
    page = ('<html><head><title>Shop</title><script type="application/ld+json">{"@type": "Product", "name": "Knee Pads Pro",'
            ' "image": ["/img/pads.jpg"], "offers": {"price": "39.95", "priceCurrency": "AUD"}}</script></head></html>')
    monkeypatch.setattr(linkpeek, "_get", lambda url, limit=None: (url, "User-agent: *\nDisallow: /secret" if url.endswith("robots.txt") else page))
    out = client.post("/api/wanted/from-link", json={"url": "https://shop.example.com/pads"}).json()
    assert out["title"] == "Knee Pads Pro" and out["price"] == 39.95 and out["image"] == "https://shop.example.com/img/pads.jpg"
    assert client.post("/api/wanted/from-link", json={"url": "https://shop.example.com/secret/x"}).status_code == 422   # robots.txt
    assert client.post("/api/wanted/from-link", json={"url": "https://boardgamegeek.com/boardgame/1"}).status_code == 422
    made = client.post("/api/wanted/from-link/save", json={"url": "https://shop.example.com/pads", "kind": "gear", "hobby": "volleyball",
                                                            "name": "Knee Pads Pro", "price": "39.95", "site": "shop.example.com"}).json()
    ex = client.get("/api/wanted/extras").json()[f"gear:{made['ref']}"]
    assert ex["link"] == "https://shop.example.com/pads" and ex["last_price"] == 39.95
    assert client.post("/api/wanted/from-link/save", json={"url": "https://x.example.com", "kind": "wish", "name": "x"}).status_code == 422


def test_open_graph_when_there_is_no_json_ld():
    found = linkpeek.parse('<meta property="og:title" content="Wingspan"><meta property="og:price:amount" content="$79.00">'
                           '<meta property="og:image" content="https://cdn.example.com/w.jpg">', "https://shop.example.com/w")
    assert found == {"title": "Wingspan", "price": 79.0, "currency": None, "image": "https://cdn.example.com/w.jpg"}



def test_a_refused_site_is_refused_after_a_redirect_too(monkeypatch):
    """BoardGameGeek and SteamHunters are never read - not even when a shop's link redirects there."""
    asked = []

    class Hop:                                         # one answer: a redirect to BoardGameGeek
        status_code, is_redirect, headers = 302, True, {"location": "https://boardgamegeek.com/boardgame/1"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, method, url):
            asked.append(url)
            return Hop()

    monkeypatch.setattr(linkpeek.httpx, "Client", Client)
    monkeypatch.setattr(linkpeek, "check_address", lambda url: None)
    try:
        REAL_GET("https://shop.example.com/game")
        raise AssertionError("should have been refused")
    except linkpeek.LinkError as e:
        assert "doesn't read" in str(e)
    assert asked == ["https://shop.example.com/game"]                    # BoardGameGeek itself was never asked


def test_odd_json_ld_shapes_are_skipped_not_a_crash():
    page = ('<script type="application/ld+json">{"@type": ["Product"], "name": "Pads", "offers": ["39.95"], '
            '"image": {"@type": "ImageObject", "url": "/p.jpg"}}</script>'
            '<script type="application/ld+json">not json</script>')
    found = linkpeek.parse(page, "https://shop.example.com/x")
    assert found == {"title": "Pads", "price": None, "currency": None, "image": "https://shop.example.com/p.jpg"}
    assert linkpeek.parse("<p>nothing here</p>", "https://shop.example.com/")["title"] is None


def test_shooting_gear_from_a_link(client):
    made = client.post("/api/wanted/from-link/save", json={"url": "https://shop.example.com/bag", "kind": "gear", "hobby": "shooting",
                                                            "name": "Rear bag", "price": "45"})
    assert made.status_code == 201, made.text
    assert client.get(f"/api/gear/{made.json()['ref']}").json()["hobby"] == "shooting"


def test_the_same_price_from_the_same_place_today_is_kept_once(client):
    from app import wanted_more
    from app.db import db
    k = kit(client)
    with db() as conn:
        for _ in range(3):
            wanted_more.record_price(conn, "model", k["model_id"], 49.95, "weekly check")
        wanted_more.record_price(conn, "model", k["model_id"], 44, "weekly check")
    assert [p["price"] for p in client.get(f"/api/wanted/model/{k['model_id']}/prices").json()] == [49.95, 44]


def test_the_weekly_check_refreshes_blue_sky_gear_only(client, monkeypatch):
    from app import wanted_more
    from app.db import db
    mine = client.post("/api/gear", json={"name": "Wade shoes", "hobby": "volleyball", "condition": "Wanted"}).json()
    other = client.post("/api/gear", json={"name": "Pads", "hobby": "volleyball", "condition": "Wanted"}).json()
    with db() as conn:
        conn.execute("UPDATE gear SET shop_id = '9', shop_name = 'Blue Sky Athletics' WHERE gear_id = %s", (mine["gear_id"],))
    monkeypatch.setattr(bluesky, "get", lambda pid: {"price": 189, "available": True})
    assert wanted_more.refresh_weekly() == 1
    ex = client.get("/api/wanted/extras").json()
    assert ex[f"gear:{mine['gear_id']}"]["in_stock"] is True and ex[f"gear:{mine['gear_id']}"]["last_source"] == "weekly check"
    assert ex[f"gear:{other['gear_id']}"]["last_price"] is None
    from app.ucp import ShopError
    monkeypatch.setattr(bluesky, "get", lambda pid: (_ for _ in ()).throw(ShopError("down")))
    assert wanted_more.refresh_weekly() == 0                                               # a shop that's down: skipped


def test_adding_each_kind_from_a_link(client, ids):
    def save(**kw):
        r = client.post("/api/wanted/from-link/save", json={"url": "https://shop.example.com/x", "name": "Thing", "price": "10", **kw})
        assert r.status_code == 201, r.text
        return r.json()["ref"]
    assert client.get(f"/api/models/{save(kind='model', site='Hobbyrama')}").json()["status"] == "Wanted"
    assert client.get(f"/api/board-games/{save(kind='game')}").json()["shop_url"] == "https://shop.example.com/x"
    wish = save(kind="wish", category_id=ids["paint"])
    assert any(w["wish_id"] == wish for w in client.get("/api/wishlist").json())
    garden = save(kind="garden")
    ex = client.get("/api/wanted/extras").json()
    assert ex[f"garden:{garden}"]["last_price"] == 10 and ex[f"wish:{wish}"]["link"] == "https://shop.example.com/x"
    r = client.post("/api/wanted/from-link/save", json={"url": "https://x.example.com", "kind": "wish", "name": "x", "category_id": 999999})
    assert r.status_code == 404


def test_undoing_a_tick_on_each_kind(client):
    game = client.post("/api/board-games", json={"name": "Azul", "status": "Wanted"}).json()
    gear = client.post("/api/gear", json={"name": "Ball", "hobby": "volleyball", "condition": "Wanted"}).json()
    for kind, ref in (("game", game["game_id"]), ("gear", gear["gear_id"])):
        client.post(f"/api/wanted/{kind}/{ref}/got", json={"paid": "20"})
    assert client.get(f"/api/board-games/{game['game_id']}").json()["status"] == "Owned"
    assert client.get(f"/api/gear/{gear['gear_id']}").json()["condition"] == "New"
    for kind, ref in (("game", game["game_id"]), ("gear", gear["gear_id"])):
        assert client.post(f"/api/wanted/{kind}/{ref}/ungot").status_code == 204
    assert client.get(f"/api/board-games/{game['game_id']}").json()["status"] == "Wanted"
    assert client.get("/api/wanted/history").json() == []
    assert client.post("/api/wanted/wish/1/ungot").status_code == 422                       # (a supply's buy isn't undone here)


ORPHANS = """SELECT (SELECT count(*) FROM wanted_extras e WHERE NOT EXISTS (
                 SELECT 1 FROM wishlist WHERE e.kind = 'wish' AND wish_id = e.ref UNION ALL
                 SELECT 1 FROM models WHERE e.kind = 'model' AND model_id = e.ref UNION ALL
                 SELECT 1 FROM board_games WHERE e.kind = 'game' AND game_id = e.ref UNION ALL
                 SELECT 1 FROM gear WHERE e.kind = 'gear' AND gear_id = e.ref UNION ALL
                 SELECT 1 FROM garden_items WHERE e.kind = 'garden' AND item_id = e.ref))
           + (SELECT count(*) FROM wanted_prices p WHERE NOT EXISTS (
                 SELECT 1 FROM wishlist WHERE p.kind = 'wish' AND wish_id = p.ref UNION ALL
                 SELECT 1 FROM models WHERE p.kind = 'model' AND model_id = p.ref UNION ALL
                 SELECT 1 FROM board_games WHERE p.kind = 'game' AND game_id = p.ref UNION ALL
                 SELECT 1 FROM gear WHERE p.kind = 'gear' AND gear_id = p.ref UNION ALL
                 SELECT 1 FROM garden_items WHERE p.kind = 'garden' AND item_id = p.ref)) AS n"""


def test_deleting_a_wanted_thing_takes_its_extras_and_prices_with_it(client, ids):
    """(90_wanted_cleanup.sql) Each of the five kinds: details and prices go with it; the bought history stays."""
    from app.db import db
    made = {
        "model": (kit(client)["model_id"], "/api/models/{}"),
        "game": (client.post("/api/board-games", json={"name": "Azul", "status": "Wanted"}).json()["game_id"], "/api/board-games/{}"),
        "gear": (client.post("/api/gear", json={"name": "Ball", "hobby": "volleyball", "condition": "Wanted"}).json()["gear_id"], "/api/gear/{}"),
        "garden": (client.post("/api/garden/items", json={"name": "Mulch", "kind": "Other", "status": "Wanted"}).json()["item_id"],
                   "/api/garden/items/{}"),
        "wish": (client.post("/api/wishlist", json={"name": "XF-1", "category_id": ids["paint"]}).json()["wish_id"], "/api/wishlist/{}"),
    }
    for kind, (ref, _) in made.items():
        client.put(f"/api/wanted/{kind}/{ref}", json={"target_price": "10"})
        client.post(f"/api/wanted/{kind}/{ref}/prices", json={"price": "12"})
    with db() as conn:
        assert conn.execute("SELECT count(*) AS n FROM wanted_prices").fetchone()["n"] == 5
    client.post(f"/api/wanted/game/{made['game'][0]}/got", json={"paid": "50"})          # (a record of a buy...)
    for kind, (ref, path) in made.items():
        assert client.delete(path.format(ref)).status_code in (200, 204), kind
    with db() as conn:
        assert conn.execute("SELECT count(*) AS n FROM wanted_extras").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM wanted_prices").fetchone()["n"] == 0
        assert conn.execute(ORPHANS).fetchone()["n"] == 0
    assert [h["name"] for h in client.get("/api/wanted/history").json()] == ["Azul"]     # (...stays)
