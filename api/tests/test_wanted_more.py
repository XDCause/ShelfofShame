"""More for the wishlist (89_wishlist_more.sql, api/app/wanted_more.py, linkpeek.py): what it's for, target prices and
their history, saving up, shop checks, ticking anything bought (+ undo), the bought history, adding from a link."""
from datetime import date

from app import bluesky, goodgames, linkpeek

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
