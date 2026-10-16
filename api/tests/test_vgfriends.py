"""Video games friends: the list (public or not), friends added by hand, comparing games (fake Steam)."""
import pytest

from app import steam, vgfriends
from app.db import db

ME, ANA, BEN, CAL = "76561198000000001", "76561198000000011", "76561198000000012", "76561198000000013"


@pytest.fixture
def fake(monkeypatch):
    state = {"list": [ANA, BEN], "private": False}
    people = {ANA: {"name": "Ana", "avatar": "https://a/ana.jpg", "profile_url": "https://s/ana", "public": True,
                    "status": "Online", "playing": "Hades"},
              BEN: {"name": "Ben", "avatar": None, "profile_url": "https://s/ben", "public": True, "status": "Offline", "playing": None},
              CAL: {"name": "Cal", "avatar": None, "profile_url": "https://s/cal", "public": False, "status": None, "playing": None}}

    def friend_ids(_me):
        if state["private"]:
            raise steam.FriendsPrivate("Your Steam friends list is private.")
        return state["list"]

    def owned(sid):
        if sid == BEN:
            raise steam.SteamError("private")
        return [{"appid": 10, "playtime_forever": 300}, {"appid": 20, "playtime_forever": 50}, {"appid": 99, "playtime_forever": 5}]

    def achievements(sid, app_id):
        return {10: [{"achieved": 1}, {"achieved": 1}], 20: [{"achieved": 1}, {"achieved": 0}, {"achieved": 0}, {"achieved": 0}]}[app_id]
    monkeypatch.setattr(steam, "friend_ids", friend_ids)
    monkeypatch.setattr(steam, "summaries", lambda ids: {i: people[i] for i in ids if i in people})
    monkeypatch.setattr(steam, "owned_games", owned)
    monkeypatch.setattr(steam, "player_achievements", achievements)
    monkeypatch.setattr(steam, "resolve", lambda text: {"cal": CAL, "me": ME}.get(text.strip()) or (_ for _ in ()).throw(steam.SteamError("No profile")))
    monkeypatch.setattr(steam, "pause", lambda: None)
    vgfriends.STATE.update(list_public=None, error=None)
    with db() as conn:
        conn.execute("INSERT INTO vg_sync (id, steam_id) VALUES (1, %s) ON CONFLICT (id) DO UPDATE SET steam_id = EXCLUDED.steam_id", (ME,))
        conn.execute("INSERT INTO vg_games (app_id, name, achievements_total, achievements_done, has_achievements) VALUES "
                     "(10, 'Celeste', 2, 1, true), (20, 'Hades', 4, 3, true), (30, 'Mine only', 5, 0, true)")
    return state


def test_the_friends_list_and_comparing(client, fake):
    r = client.post("/api/videogames/friends/refresh").json()
    assert r["list_public"] is True and [f["name"] for f in r["friends"]] == ["Ana", "Ben"]   # playing now first
    assert r["friends"][0]["playing"] == "Hades"
    ana = client.post(f"/api/videogames/friends/{ANA}/compare").json()     # (the test client runs it before answering)
    ana = client.get(f"/api/videogames/friends/{ANA}").json()
    games = {g["name"]: g for g in ana["games"]}
    assert set(games) == {"Celeste", "Hades"}                               # only games you both have with achievements
    assert (games["Celeste"]["their_percent"], games["Celeste"]["my_percent"]) == (100.0, 50.0)
    assert (ana["you_ahead"], ana["they_ahead"], ana["their_perfect"], ana["games_owned"]) == (1, 1, 1, 3)
    ben = client.post(f"/api/videogames/friends/{BEN}/compare").json()
    ben = client.get(f"/api/videogames/friends/{BEN}").json()
    assert "private" in ben["compare_error"] and ben["games"] == []


def test_a_private_list_and_friends_added_by_hand(client, fake):
    fake["private"] = True
    r = client.post("/api/videogames/friends/refresh?force=true").json()
    assert r["list_public"] is False and "private" in r["error"] and r["friends"] == []
    cal = client.post("/api/videogames/friends", json={"profile": "cal"}).json()
    assert (cal["name"], cal["by_hand"], cal["public"]) == ("Cal", True, False)
    assert client.post("/api/videogames/friends", json={"profile": "me"}).status_code == 422
    assert client.post("/api/videogames/friends", json={"profile": "nobody"}).status_code == 422
    # The list is public again: Ana and Ben join; Cal stays (added by hand).
    fake["private"] = False
    names = [f["name"] for f in client.post("/api/videogames/friends/refresh?force=true").json()["friends"]]
    assert sorted(names) == ["Ana", "Ben", "Cal"]
    # Removing: one added by hand goes; one from the list is hidden; someone who leaves the list goes.
    assert client.delete(f"/api/videogames/friends/{CAL}").status_code == 204
    client.delete(f"/api/videogames/friends/{BEN}")
    r = client.get("/api/videogames/friends").json()
    assert [f["name"] for f in r["friends"]] == ["Ana"] and r["hidden"] == 1
    fake["list"] = [BEN]
    client.post("/api/videogames/friends/refresh?force=true")
    with db() as conn:
        assert [x["steam_id"] for x in conn.execute("SELECT steam_id FROM vg_friends").fetchall()] == [BEN]
