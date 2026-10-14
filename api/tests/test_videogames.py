"""Video games: syncing Steam games and achievements (with a fake Steam), the dashboard, activity."""
from datetime import datetime, timezone

import pytest

from app import steam

ME = "76561198000000001"
T = lambda d: int(datetime(2026, 10, d, 20, 0, tzinfo=timezone.utc).timestamp())  # noqa: E731


class FakeSteam:
    """Stands in for steam.py: three games - one 100%, one part-done, one without achievements."""
    def __init__(self):
        self.calls = []
        self.games = [
            {"appid": 10, "name": "Celeste", "img_icon_url": "abc", "playtime_forever": 900, "rtime_last_played": T(10)},
            {"appid": 20, "name": "Hades", "img_icon_url": "def", "playtime_forever": 3000, "rtime_last_played": T(12)},
            {"appid": 30, "name": "Free Demo", "playtime_forever": 5, "rtime_last_played": T(1)},
        ]
        self.mine = {
            10: [{"apiname": "A", "achieved": 1, "unlocktime": T(3)}, {"apiname": "B", "achieved": 1, "unlocktime": T(10)}],
            20: [{"apiname": "X", "achieved": 1, "unlocktime": T(12)}, {"apiname": "Y", "achieved": 0, "unlocktime": 0},
                 {"apiname": "Z", "achieved": 0, "unlocktime": 0}],
        }
        self.names = {
            10: [{"name": "A", "displayName": "First Steps", "description": "Start", "icon": "i/a.jpg", "icongray": "g/a.jpg"},
                 {"name": "B", "displayName": "Summit", "description": "Finish", "icon": "i/b.jpg", "icongray": "g/b.jpg"}],
            20: [{"name": "X", "displayName": "Escape", "description": "Get out", "icon": "i/x.jpg"},
                 {"name": "Y", "displayName": "Secret", "hidden": 1, "icon": "i/y.jpg"},
                 {"name": "Z", "displayName": "Godlike", "description": "Max heat", "icon": "i/z.jpg"}],
        }
        self.rarity = {10: {"A": 80.5, "B": 4.2}, 20: {"X": 60.0, "Y": 12.0, "Z": 0.9}}

    def install(self, monkeypatch):
        def log(name, fn):
            def wrapped(*a):
                self.calls.append((name, *a))
                return fn(*a)
            return wrapped

        def mine(_steam_id, app_id):
            if app_id not in self.mine:
                raise steam.NoStats("Requested app has no stats")
            return self.mine[app_id]

        def resolve(profile):
            if profile.strip() != "SomeGamer":
                raise steam.SteamError(f"No Steam profile called '{profile}'.")
            return ME

        monkeypatch.setattr(steam, "key", lambda: "fake-key")
        monkeypatch.setattr(steam, "resolve", resolve)
        monkeypatch.setattr(steam, "persona", lambda _id: "SomeGamer")
        monkeypatch.setattr(steam, "owned_games", log("owned_games", lambda _id: self.games))
        monkeypatch.setattr(steam, "player_achievements", log("player_achievements", mine))
        monkeypatch.setattr(steam, "schema", log("schema", lambda app_id: self.names.get(app_id, [])))
        monkeypatch.setattr(steam, "global_percentages", log("rarity", lambda app_id: self.rarity.get(app_id, {})))
        # The store knows Hades' new-style picture; Celeste falls back to the old address; the demo has none.
        pictures = {20: "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/20/abc123/header.jpg"}
        monkeypatch.setattr(steam, "header_pictures", log("pictures", lambda ids: {i: pictures.get(i) for i in ids}))
        monkeypatch.setattr(steam, "store_items", log("store", lambda ids: {
            i: {"name": "Counter-Strike 2", "header": "https://shared.akamai.steamstatic.com/cs2.jpg"} for i in ids if i == 730}))
        return self


@pytest.fixture
def fake(monkeypatch):
    return FakeSteam().install(monkeypatch)


def setup(client):
    r = client.put("/api/videogames/account", json={"profile": "SomeGamer"})
    assert r.status_code == 200, r.text
    return r.json()


def test_setting_the_profile_syncs_every_game(client, fake):
    account = setup(client)
    assert (account["steam_id"], account["persona_name"]) == (ME, "SomeGamer")
    games = {g["name"]: g for g in client.get("/api/videogames").json()}
    assert games["Celeste"]["percent"] == 100                          # 100% when the last one was unlocked:
    assert datetime.fromisoformat(games["Celeste"]["completed_at"]).timestamp() == T(10)
    assert (games["Hades"]["achievements_done"], games["Hades"]["achievements_total"], games["Hades"]["left_to_get"]) == (1, 3, 2)
    assert games["Free Demo"]["has_achievements"] is False and games["Free Demo"]["percent"] is None
    assert games["Hades"]["header_url"].endswith("/apps/20/abc123/header.jpg")       # the store API's address
    assert games["Hades"]["icon_url"].endswith("/apps/20/def.jpg")
    assert client.get("/api/videogames/account").json()["last_sync_at"]
    assert client.put("/api/videogames/account", json={"profile": "nobody"}).status_code == 422


def test_one_game_with_its_achievements(client, fake):
    setup(client)
    hades = client.get("/api/videogames/20").json()
    names = [(a["name"], a["achieved"], float(a["global_percent"])) for a in hades["achievements"]]
    assert names == [("Escape", True, 60.0), ("Secret", False, 12.0), ("Godlike", False, 0.9)]   # unlocked first
    assert hades["achievements"][1]["hidden"] is True and hades["achievements"][1]["description"] is None
    assert client.get("/api/videogames/999").status_code == 404


def test_the_dashboard_summary(client, fake):
    setup(client)
    s = client.get("/api/videogames/summary").json()
    assert (s["games"], s["perfect"], s["started"], s["achievements"], s["achievements_total"]) == (3, 1, 1, 3, 5)
    assert [g["name"] for g in s["closest"]] == ["Hades"]
    assert [a["name"] for a in s["recent"]] == ["Escape", "Summit", "First Steps"]
    assert [a["name"] for a in s["rarest"]] == ["Summit", "Escape", "First Steps"]     # 4.2%, 60%, 80.5%
    assert [g["name"] for g in s["recent_perfect"]] == ["Celeste"]


def test_a_later_sync_only_reads_games_played_since(client, fake):
    setup(client)
    fake.calls.clear()
    fake.games[1]["rtime_last_played"] = T(13)                        # played Hades again...
    fake.mine[20][1] = {"apiname": "Y", "achieved": 1, "unlocktime": T(13)}   # ...and got the secret one
    assert client.post("/api/videogames/sync").status_code == 202
    read = [c[2] for c in fake.calls if c[0] == "player_achievements"]
    assert read == [20]                                               # not Celeste, not the demo
    assert not [c for c in fake.calls if c[0] == "schema"]            # names already known
    assert client.get("/api/videogames/20").json()["achievements_done"] == 2
    fake.calls.clear()
    client.post("/api/videogames/sync?full=true")
    assert sorted(c[2] for c in fake.calls if c[0] == "player_achievements") == [10, 20, 30]


def test_hiding_a_game(client, fake):
    setup(client)
    client.patch("/api/videogames/30", json={"hidden": True})
    assert [g["name"] for g in client.get("/api/videogames").json()] == ["Hades", "Celeste"]
    assert [g["name"] for g in client.get("/api/videogames?show=hidden").json()] == ["Free Demo"]
    assert client.get("/api/videogames/summary").json()["games"] == 2
    assert [g["name"] for g in client.get("/api/videogames?show=perfect").json()] == ["Celeste"]


def test_sync_needs_a_profile_and_explains_problems(client, fake, monkeypatch):
    assert client.post("/api/videogames/sync").status_code == 409            # no profile yet
    setup(client)

    def private(_id):
        raise steam.SteamError("Steam didn't share the games list. Set your profile's Game details to Public.")
    monkeypatch.setattr(steam, "owned_games", private)
    client.post("/api/videogames/sync")
    account = client.get("/api/videogames/account").json()
    assert "Game details to Public" in account["last_error"] and "Public" in account["sync"]["error"]


def test_unlocks_and_perfect_games_are_activity_and_mentionable(client, fake):
    setup(client)
    feed = [(f["verb"], f["title"], f["detail"]) for f in client.get("/api/activity?limit=50").json()
            if f["kind"] == "videogame"]
    assert ("Perfected", "Celeste", "100% · 2 achievements") in feed
    assert ("Unlocked", "Hades", "Escape") in feed
    assert ("Unlocked", "Celeste", "Summit") in feed and ("Unlocked", "Celeste", "First Steps") in feed  # different days
    found = client.get("/api/journal/mentionable?q=hade").json()
    assert {"kind": "videogame", "id": 20, "label": "Hades", "what": "Video game"} in found


def test_the_real_client_reads_steams_answers(monkeypatch):
    """steam.py itself, against Steam's documented response shapes (no network)."""
    real_key = steam.key
    answers = {
        "ISteamUser/ResolveVanityURL/v1/": (200, {"response": {"steamid": ME, "success": 1}}),
        "IPlayerService/GetOwnedGames/v1/": (200, {"response": {}}),                     # a private profile
        "ISteamUserStats/GetPlayerAchievements/v1/": (400, {"playerstats": {"error": "Requested app has no stats", "success": False}}),
        "ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/":
            (200, {"achievementpercentages": {"achievements": [{"name": "A", "percent": "12.5"}]}}),
    }
    asked = {}
    monkeypatch.setattr(steam, "key", lambda: "fake-key")
    monkeypatch.setattr(steam, "_get", lambda path, params, with_key=True: asked.setdefault(path, params) and answers[path])
    assert steam.resolve("https://steamcommunity.com/id/SomeGamer/games") == ME
    assert steam.resolve(ME) == ME
    with pytest.raises(steam.SteamError, match="Public"):
        steam.owned_games(ME)
    # Small "unvetted" games are left out unless asked for (SteamHunters counts them).
    assert asked["IPlayerService/GetOwnedGames/v1/"]["skip_unvetted_apps"] == 0
    with pytest.raises(steam.NoStats):
        steam.player_achievements(ME, 10)
    assert steam.global_percentages(10) == {"A": 12.5}
    monkeypatch.delenv("STEAM_API_KEY", raising=False)
    with pytest.raises(steam.SteamError, match="STEAM_API_KEY"):
        real_key()


def test_pictures_are_looked_up_once_and_again_on_a_full_sync(client, fake):
    setup(client)
    looked_up = [c for c in fake.calls if c[0] == "pictures"]
    assert len(looked_up) == 1 and sorted(looked_up[0][1]) == [10, 20, 30]          # every game, one batch
    games = {g["name"]: g for g in client.get("/api/videogames?show=all").json()}
    assert games["Celeste"]["header_url"].endswith("/apps/10/header.jpg")         # none in the store: the old address
    fake.calls.clear()
    client.post("/api/videogames/sync")
    assert not [c for c in fake.calls if c[0] == "pictures"]                       # known already
    client.post("/api/videogames/sync?full=true")
    assert [sorted(c[1]) for c in fake.calls if c[0] == "pictures"] == [[10, 20, 30]]
    feed = {f["title"]: f["photo_url"] for f in client.get("/api/activity?limit=50").json() if f["kind"] == "videogame"}
    assert feed["Hades"].endswith("/abc123/header.jpg")


def test_the_store_api_answer_becomes_picture_addresses(monkeypatch):
    answer = {"response": {"store_items": [
        {"appid": 3672720, "assets": {"asset_url_format": "steam/apps/3672720/${FILENAME}?t=1791782793",
                                      "header": "298ca32c/header.jpg"}},
        {"appid": 413150, "assets": {"asset_url_format": "steam/apps/413150/${FILENAME}?t=1", "header": "header.jpg"}},
        {"appid": 99, "success": 2}]}}
    monkeypatch.setattr(steam, "key", lambda: "fake-key")
    monkeypatch.setattr(steam, "_get", lambda path, params, with_key=True: (200, answer))
    got = steam.header_pictures([3672720, 413150, 99])
    assert got[3672720] == ("https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/3672720/"
                            "298ca32c/header.jpg?t=1791782793")
    assert got[413150].endswith("/steam/apps/413150/header.jpg?t=1") and got[99] is None


def test_profile_completion_against_the_goal(client, fake):
    """Started games only: Celeste 2/2 (100%) and Hades 1/3 (33.3%) -> average 66.7%, total 3/5 = 60%.
    A game with none unlocked isn't counted."""
    fake.games.append({"appid": 40, "name": "Untouched", "playtime_forever": 0, "rtime_last_played": 0})
    fake.mine[40] = [{"apiname": "Q", "achieved": 0, "unlocktime": 0}, {"apiname": "R", "achieved": 0, "unlocktime": 0}]
    setup(client)
    goal = client.get("/api/videogames/summary").json()["goal"]
    assert (goal["percent"], goal["total_percent"], goal["achievements"], goal["achievements_total"]) == (66.7, 60.0, 3, 5)
    assert (goal["goal_percent"], goal["reached"], goal["points_to_go"]) == (50, True, 0)
    goal = client.put("/api/videogames/goal", json={"percent": 100}).json()["goal"]
    assert (goal["reached"], goal["points_to_go"], goal["plan"]) == (False, 33.3, {"games": 1, "achievements": 2})
    assert client.put("/api/videogames/goal", json={"percent": 0}).status_code == 422
    assert client.put("/api/videogames/goal", json={"percent": 101}).status_code == 422
    client.patch("/api/videogames/20", json={"hidden": True})            # hidden games don't count
    goal = client.get("/api/videogames/summary").json()["goal"]
    assert (goal["percent"], goal["reached"]) == (100.0, True)


def test_the_quickest_route_to_the_goal():
    from app.videogames import goal_progress
    # Three started games: 1/2 (50%), 9/10 (90%), 1/100 (1%) average 47%; the total is 11/112.
    games = [(1, 2), (9, 10), (1, 100)]
    goal = goal_progress(games, 30, 50)
    assert (goal["percent"], goal["total_percent"], goal["points_to_go"]) == (47.0, 9.8, 3.0)
    # Finish the game with 1 left (90% -> 100%): +3.3 points -> 50.3%. One game, one achievement.
    assert goal["plan"] == {"games": 1, "achievements": 1}
    assert goal["days_at_pace"] == 1                                       # a day's pace (1 a day)
    goal = goal_progress(games, 0, 90)                                     # all three 100%: 100% average
    assert goal["plan"] == {"games": 3, "achievements": 101} and goal["days_at_pace"] is None
    assert goal_progress([], 0, 50)["percent"] == 0.0 and goal_progress([], 0, 50)["plan"] is None


def test_stats_for_the_charts(client, fake):
    setup(client)
    s = client.get("/api/videogames/stats?months=3").json()
    assert len(s["by_month"]) == 3 and s["by_month"][-1]["month"] == datetime.now().strftime("%Y-%m")
    rarity = {b["label"]: b["count"] for b in s["rarity"]}
    assert rarity == {"Under 1%": 0, "1–5%": 1, "5–10%": 0, "10–20%": 0, "20–50%": 0, "50% or more": 2}
    completion = {b["label"]: b["count"] for b in s["completion"]}
    assert (completion["25–49%"], completion["100%"], completion["Under 10%"]) == (1, 1, 0)   # Hades 33%, Celeste
    assert [g["name"] for g in s["most_played"]] == ["Hades", "Celeste", "Free Demo"]
    assert client.get("/api/videogames/stats?months=0").status_code == 422


def test_adding_a_game_the_owned_list_leaves_out(client, fake):
    """Counter-Strike 2: free, so not in the owned list, but you have its one achievement."""
    setup(client)
    fake.mine[730] = [{"apiname": "WIN", "achieved": 1, "unlocktime": T(5)}]
    fake.names[730] = [{"name": "WIN", "displayName": "A New Beginning", "icon": "i/win.jpg"}]
    r = client.post("/api/videogames/extra", json={"game": "https://store.steampowered.com/app/730/CounterStrike_2/"})
    assert r.status_code == 201, r.text
    cs2 = r.json()
    assert (cs2["name"], cs2["extra"], cs2["percent"], cs2["header_url"]) == (
        "Counter-Strike 2", True, 100, "https://shared.akamai.steamstatic.com/cs2.jpg")
    s = client.get("/api/videogames/summary").json()
    assert (s["perfect"], s["goal"]["achievements"]) == (2, 4)                    # it counts like any game
    assert client.post("/api/videogames/extra", json={"game": "730"}).status_code == 409   # already there
    # Synced every time (no "last played" for it), even when nothing else is.
    fake.calls.clear()
    client.post("/api/videogames/sync")
    assert [c[2] for c in fake.calls if c[0] == "player_achievements"] == [730]
    assert client.delete("/api/videogames/extra/20").status_code == 404           # library games: hide instead
    assert client.delete("/api/videogames/extra/730").status_code == 204
    assert client.get("/api/videogames/730").status_code == 404


def test_adding_a_game_explains_what_went_wrong(client, fake):
    assert client.post("/api/videogames/extra", json={"game": "730"}).status_code == 409    # no profile yet
    setup(client)
    assert client.post("/api/videogames/extra", json={"game": "a game"}).status_code == 422
    assert "no achievements" in client.post("/api/videogames/extra", json={"game": "999"}).json()["detail"]
    fake.mine[731] = [{"apiname": "A", "achieved": 0, "unlocktime": 0}]
    assert "haven't unlocked" in client.post("/api/videogames/extra", json={"game": "731"}).json()["detail"]


def test_app_ids_from_links():
    assert steam.app_id_from("730") == 730
    assert steam.app_id_from("https://store.steampowered.com/app/730/CounterStrike_2/") == 730
    assert steam.app_id_from("https://steamcommunity.com/profiles/1/stats/730/achievements") == 730
    assert steam.app_id_from("Counter-Strike") is None
