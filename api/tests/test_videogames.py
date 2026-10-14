"""Video games: syncing Steam games and achievements (with a fake Steam), the dashboard, activity."""
from datetime import datetime, timezone

import pytest

from app import exophase, othergames, steam, steamhunters
from app.db import db

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
        # SteamHunters: Celeste 5,685 of 23,079 players 100%'d it (24.6%), median 2,994 min; it doesn't know Hades.
        community = {10: {"sh_median_minutes": 2994, "sh_fastest_minutes": 214, "sh_players_perfected": 5685,
                          "sh_players_started": 23079, "sh_points": 4669, "sh_has_dlc": False}}
        monkeypatch.setattr(steamhunters, "game", log("community", lambda app_id: community.get(app_id)))
        # Exophase: Hades' Godlike comes with a DLC (SteamHunters doesn't know Hades, so it's looked up;
        # Celeste has no DLC, so it isn't).
        monkeypatch.setattr(steamhunters, "dlc_names", lambda app_id: ["Hades - Heat Pack"])
        monkeypatch.setattr(exophase, "dlc_of", log("dlc", lambda app_id, name, total, dlcs: (
            "https://www.exophase.com/game/hades-steam/achievements/", {"godlike": "Heat Pack"}) if app_id == 20 else ("", {})))
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


def test_what_changed_this_week():
    from app.videogames import week_change
    games = [{"done": 10, "total": 10, "done_then": 8},     # 100% this week
             {"done": 5, "total": 20, "done_then": 5},      # nothing this week
             {"done": 3, "total": 30, "done_then": 0}]      # started this week (pulls the average down)
    week = week_change(games)
    assert (week["achievements"], week["perfect"], week["in_progress"]) == (5, 1, 0)   # one in, one out
    # average then: (80 + 25) / 2 = 52.5; now: (100 + 25 + 10) / 3 = 45.0
    assert week["percent"] == -7.5
    # total then: 13 / 30 = 43.3%; now: 18 / 60 = 30.0%
    assert week["total_percent"] == -13.3


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


def test_how_other_players_did_from_steamhunters(client, fake):
    """Started games only (not the demo), saved; a game SteamHunters doesn't know is remembered as read."""
    setup(client)
    assert sorted(c[1] for c in fake.calls if c[0] == "community") == [10, 20]
    celeste = client.get("/api/videogames/10").json()
    assert (celeste["sh_median_minutes"], celeste["sh_fastest_minutes"], float(celeste["perfect_rate"])) == (2994, 214, 24.6)
    assert float(celeste["rarest_percent"]) == 4.2                       # Steam's cross-check: its rarest achievement
    hades = client.get("/api/videogames/20").json()
    assert hades["perfect_rate"] is None and hades["sh_synced_at"]           # not known there, but not asked again...
    fake.calls.clear()
    client.post("/api/videogames/sync")
    assert not [c for c in fake.calls if c[0] == "community"]               # ...nothing played since: none asked
    client.post("/api/videogames/sync?full=true")
    assert not [c for c in fake.calls if c[0] == "community"]               # a full sync skips ones read today...
    with db() as conn:
        conn.execute("UPDATE vg_games SET sh_synced_at = now() - interval '2 days'")
    client.post("/api/videogames/sync?full=true")
    assert sorted(c[1] for c in fake.calls if c[0] == "community") == [10, 20]   # ...but not older ones


def test_steamhunters_being_down_doesnt_spoil_the_sync(client, fake, monkeypatch):
    def down(_app_id):
        raise steamhunters.Unavailable("SteamHunters didn't answer (HTTP 503).")
    monkeypatch.setattr(steamhunters, "game", down)
    setup(client)
    account = client.get("/api/videogames/account").json()
    assert account["last_error"] is None and "didn't answer" in account["sync"]["message"]
    assert client.get("/api/videogames/summary").json()["perfect"] == 1     # Steam's part is saved
    monkeypatch.setattr(steamhunters, "game", lambda app_id: None)
    client.post("/api/videogames/sync")                                      # never read: tried again
    assert client.get("/api/videogames/10").json()["sh_synced_at"]


def test_the_steamhunters_client_reads_its_answers(monkeypatch):
    import httpx

    def answer(status, body, kind="application/json"):
        return lambda url: httpx.Response(status, content=body.encode(), headers={"content-type": kind})
    monkeypatch.setattr(steamhunters, "_get", answer(200, '{"medianCompletionTime": 2994, "playersPerfectedCount": 5685, '
                                                         '"playersStartedCount": 23079, "points": 4669}'))
    got = steamhunters.game(504230)
    assert (got["sh_median_minutes"], got["sh_players_perfected"], got["sh_fastest_minutes"]) == (2994, 5685, None)
    monkeypatch.setattr(steamhunters, "_get", answer(404, "<html>"))
    assert steamhunters.game(1) is None
    monkeypatch.setattr(steamhunters, "_get", answer(403, "<html>Just a moment...</html>", "text/html"))   # a bot check
    with pytest.raises(steamhunters.Unavailable):
        steamhunters.game(1)


def test_which_achievements_come_with_a_dlc(client, fake):
    """Started games with DLC (or unknown to SteamHunters) are looked up once; full sync again."""
    setup(client)
    assert [c[1] for c in fake.calls if c[0] == "dlc"] == [20]          # not Celeste (no DLC), not the demo
    hades = {a["name"]: a["dlc"] for a in client.get("/api/videogames/20").json()["achievements"]}
    assert hades == {"Escape": None, "Secret": None, "Godlike": "Heat Pack"}
    games = {g["name"]: g for g in client.get("/api/videogames").json()}
    assert (games["Hades"]["dlc_count"], games["Hades"]["dlc_achievements"], games["Hades"]["dlc_done"]) == (1, 1, 0)
    assert games["Celeste"]["dlc_count"] == 0                             # the list's DLC badge
    assert "exo_url" not in games["Hades"] and "synced_at" not in games["Hades"]     # the list leaves out bookkeeping
    assert set(client.get("/api/videogames/summary").json()["week"]) == {
        "achievements", "perfect", "in_progress", "percent", "total_percent"}
    fake.calls.clear()
    client.post("/api/videogames/sync")
    assert not [c for c in fake.calls if c[0] == "dlc"]                  # read already
    fake.names[20].append({"name": "W", "displayName": "New One"})       # an update adds an achievement:
    fake.mine[20].append({"apiname": "W", "achieved": 0, "unlocktime": 0})
    fake.games[1]["rtime_last_played"] = T(13)
    client.post("/api/videogames/sync")
    assert [c[1] for c in fake.calls if c[0] == "dlc"] == [20]           # ...looked up again
    fake.calls.clear()
    client.post("/api/videogames/sync?full=true")
    assert not [c for c in fake.calls if c[0] == "dlc"]                  # a full sync skips recent DLC lists...
    with db() as conn:
        conn.execute("UPDATE vg_games SET exo_synced_at = now() - interval '31 days'")
    client.post("/api/videogames/sync?full=true")
    assert [c[1] for c in fake.calls if c[0] == "dlc"] == [20]           # ...but not month-old ones


def test_exophase_being_down_doesnt_spoil_the_sync(client, fake, monkeypatch):
    def down(*_a):
        raise exophase.Unavailable("Exophase didn't answer (HTTP 503).")
    monkeypatch.setattr(exophase, "dlc_of", down)
    setup(client)
    account = client.get("/api/videogames/account").json()
    assert account["last_error"] is None and "Exophase didn't answer (HTTP 503). Some games' DLC lists wait" in account["sync"]["message"]
    assert client.get("/api/videogames/20").json()["exo_synced_at"] is None    # tried again next time


# A made-up page in Exophase's layout: the main game's list, then one list per DLC under its heading.
EXO_PAGE = """<html><body>
<a href="https://store.steampowered.com/app/4242">Store</a>
<ul class="row list-unordered-base steam achievement">
  <li class="award"><div class="award-title"><a href="#">First Steps</a></div></li>
  <li class="award secret"><div class="award-title"><a href="#">Don’t Look Back</a></div></li>
</ul>
<h3 class="dlc-add-on"><span>Space Game: The Moon Expansion Achievements</span></h3>
<ul class="row list-unordered-base steam achievement">
  <li class="award"><div class="award-title"><a href="#">Moonwalker</a></div></li>
</ul>
<h3 class="dlc-add-on"><span>Update #2 Achievements</span></h3>
<ul class="row list-unordered-base steam achievement">
  <li class="award"><div class="award-title"><a href="#">Bonus!</a></div></li>
</ul>
</body></html>"""


def test_the_exophase_reader(monkeypatch):
    import httpx

    assert exophase.key("Don’t Look Back") == exophase.key("dont look back") == "dontlookback"
    assert exophase.parse(EXO_PAGE, "Space Game") == [
        (None, "First Steps"), (None, "Don’t Look Back"), ("The Moon Expansion", "Moonwalker"), ("Update #2", "Bonus!")]
    dlcs = ["Space Game - The Moon Expansion", "Space Game Soundtrack"]   # a free update isn't a DLC:
    assert exophase.is_dlc("The Moon Expansion", "Space Game", dlcs) and not exophase.is_dlc("Update #2", "Space Game", dlcs)
    assert exophase.is_dlc("Spaced Out!", "Oxygen Not Included", ["Oxygen Not Included - Spaced Out!"])
    assert exophase.dlc_name("Space Game™ - Moon Achievements", "Space Game™") == "Moon"
    for heading, game, short in [
        ("Far Cry® 5 - Dead Living Zombies", "Far Cry 5", "Dead Living Zombies"),
        ("Just Cause™ 3 DLC: Mech Land Assault", "Just Cause 3", "Mech Land Assault"),
        ("Fallout 4 Far Harbor", "Fallout 4", "Far Harbor"),
        ("The Binding of Isaac: Afterbirth+", "The Binding of Isaac: Rebirth", "Afterbirth+"),
        ("Call of Duty®: Black Ops III - Zombies Chronicles", "Call of Duty: Black Ops III", "Zombies Chronicles"),
        ("Call of Duty: WWII - Shadow War: DLC Pack 4", "Call of Duty: WWII - Multiplayer", "Shadow War: DLC Pack 4"),
        ("Overture", "Lies of P", "Overture"),
    ]:
        assert exophase.dlc_name(heading, game) == short, heading
    assert exophase.links_to(EXO_PAGE, 4242) and not exophase.links_to(EXO_PAGE, 424)

    found = {"games": {"list": [
        {"title": "Space Game", "environment_slug": "apple", "endpoint_awards": "https://x/space-game-apple/"},
        {"title": "Space Game VR", "environment_slug": "steam", "endpoint_awards": "https://x/space-game-vr-steam/", "total_awards": 4},
        {"title": "Space Game", "environment_slug": "steam", "endpoint_awards": "https://x/space-game-steam/", "total_awards": 4},
    ]}}
    pages = {"https://x/space-game-steam/": EXO_PAGE, "https://x/space-game-vr-steam/": "<a href='https://store.steampowered.com/app/9'></a>"}
    asked = []

    def get(url, params=None):
        asked.append(url)
        if url == exophase.SEARCH:
            assert params["q"] == "Space Game"                                   # the ™ dropped for the search
            return httpx.Response(200, json=found)
        return httpx.Response(200, text=pages[url])
    monkeypatch.setattr(exophase, "_get", get)
    url, groups = exophase.dlc_of(4242, "Space Game™", 4, dlcs)
    assert url == "https://x/space-game-steam/" and asked[1] == url                # same name first, not the VR one
    assert groups == {"firststeps": None, "dontlookback": None, "moonwalker": "The Moon Expansion", "bonus": None}
    assert exophase.dlc_of(77, "Space Game", 4, dlcs) == ("", {})                          # no page links to app 77
    monkeypatch.setattr(exophase, "_get", lambda url, params=None: httpx.Response(503, text="busy"))
    with pytest.raises(exophase.Unavailable):
        exophase.dlc_of(4242, "Space Game", 4, dlcs)


def test_the_steamhunters_dlc_list(monkeypatch):
    import httpx
    related = [{"appId": 1, "name": "Space Game", "typeString": "game"}, {"appId": 2, "name": "Space Game - Moon", "typeString": "DLC"},
               {"appId": 3, "name": "Space Game Trailer", "typeString": "Media"}]
    monkeypatch.setattr(steamhunters, "_get", lambda url: httpx.Response(200, json=related))
    assert steamhunters.dlc_names(1) == ["Space Game - Moon"]


def test_a_slow_answer_is_tried_once_more(monkeypatch):
    """SteamHunters and Exophase are sometimes slow for a moment: one more try 5 s later, then give up."""
    import httpx
    import time
    monkeypatch.undo()                                  # the real _get (conftest's stand-in refuses)
    for fresh in (steamhunters, exophase):
        tries = []

        def get(url, **_k):
            tries.append(url)
            if len(tries) == 1:
                raise httpx.ReadTimeout("slow")
            return httpx.Response(200, text="ok")
        monkeypatch.setattr(fresh.httpx, "get", get)
        monkeypatch.setattr(time, "sleep", lambda s: None)
        assert fresh._get("https://example.test/a").text == "ok" and len(tries) == 2

        def always_slow(url, **_k):
            raise httpx.ReadTimeout("slow")
        monkeypatch.setattr(fresh.httpx, "get", always_slow)
        with pytest.raises(fresh.Unavailable, match="timed out twice"):
            fresh._get("https://example.test/b")


def test_streaks_of_days_with_an_unlock():
    from datetime import date
    from app.videogames import streaks
    d = lambda day: date(2026, 10, day)  # noqa: E731
    days = [d(1), d(2), d(3), d(3), d(7), d(8), d(12), d(13)]
    assert streaks(days, d(13)) == {"current": 2, "longest": 3, "longest_end": d(3), "unlocked_today": True}
    assert streaks(days, d(14))["current"] == 2          # today isn't over: yesterday keeps it alive
    assert streaks(days, d(15))["current"] == 0
    assert streaks([], d(15)) == {"current": 0, "longest": 0, "longest_end": None, "unlocked_today": False}


def test_quick_wins_are_the_least_time_left():
    from app.videogames import quick_wins
    game = lambda app_id, median, left, total, rate: {  # noqa: E731
        "app_id": app_id, "sh_median_minutes": median, "left_to_get": left, "achievements_total": total,
        "perfect_rate": rate, "header_url": "", "icon_hash": None}
    ranked = quick_wins([game(1, 6000, 30, 60, 10), game(2, 600, 1, 10, 50), game(3, 60, 59, 60, 5)])
    assert [(g["app_id"], g["minutes_left"]) for g in ranked] == [(3, 59), (2, 60), (1, 3000)]


def test_unobtainable_achievements_dont_count(client, fake, monkeypatch):
    """Hades' Godlike can't be earned any more: Hades is then 1 of 2; unlocking Secret makes it 100%."""
    monkeypatch.setattr(steamhunters, "game", lambda app_id: {"sh_unobtainable": 1} if app_id == 20 else None)
    asked = []
    monkeypatch.setattr(steamhunters, "unobtainable", lambda app_id: asked.append(app_id) or {"Z"})
    setup(client)
    assert asked == [20]                                     # only games SteamHunters says have some
    hades = client.get("/api/videogames/20").json()
    assert (hades["achievements_done"], hades["achievements_total"], hades["unobtainable_count"]) == (1, 2, 1)
    assert [a["name"] for a in hades["achievements"] if a["unobtainable"]] == ["Godlike"]
    fake.mine[20][1].update(achieved=1, unlocktime=T(13))    # Secret
    fake.games[1]["rtime_last_played"] = T(13)
    client.post("/api/videogames/sync")
    hades = client.get("/api/videogames/20").json()
    assert hades["percent"] == 100 and hades["completed_at"]


def test_a_month_recap_and_the_unlock_calendar(client, fake):
    setup(client)
    r = client.get("/api/videogames/recap?month=2026-10").json()
    assert (r["month"], r["first"], r["achievements"], r["games"], r["previous"]) == ("2026-10", "2026-10", 3, 2, 0)
    assert [g["name"] for g in r["perfect"]] == ["Celeste"]
    assert r["rarest"][0]["name"] == "Summit" and r["top_games"][0]["name"] == "Celeste"
    assert client.get("/api/videogames/recap?month=2026-09").json()["achievements"] == 0
    assert client.get("/api/videogames/recap?month=Oct").status_code == 422
    stats = client.get("/api/videogames/stats").json()
    assert set(stats["streak"]) == {"current", "longest", "longest_end", "unlocked_today"} and "days" in stats



# ---- other platforms: Epic and Ubisoft from an Exophase profile ----------------------------------
EPIC = [{"source_id": "1", "name": "Supraland", "picture_url": "https://m.exophase.com/epic/s.png",
         "page_url": "https://x/supraland-epic/achievements/", "exo_done": 1, "exo_total": 2, "exo_minutes": None,
         "last_played": T(5), "exo_completed_at": None},
        {"source_id": "2", "name": "Tiny Game", "picture_url": None, "page_url": None,
         "exo_done": 5, "exo_total": 5, "exo_minutes": 90, "last_played": T(6), "exo_completed_at": T(6)}]
UBISOFT = [{"source_id": "9", "name": "Rainbow Six Siege X", "picture_url": None, "page_url": None,
            "exo_done": 0, "exo_total": 34, "exo_minutes": None, "last_played": T(7), "exo_completed_at": None}]
SIEGE = [{"name": "ACH_1", "displayName": "Old School", "description": "Win", "icon": "i/1.jpg", "icongray": "g/1.jpg"},
         {"name": "ACH_2", "displayName": "Full Roster", "description": "All", "icon": "i/2.jpg"},
         {"name": "ACH_3", "displayName": "Secret", "hidden": 1, "icon": "i/3.jpg"}]


@pytest.fixture
def exo(monkeypatch):
    """A fake Exophase profile (Epic + Ubisoft) and Steam versions: Supraland 813630, Siege 359550."""
    asked = []
    monkeypatch.setattr(exophase, "profile_players", lambda name: {"epic": 11, "uplay": 22} if name == "SomeGamer" else {})
    monkeypatch.setattr(exophase, "player_games", lambda player, env: asked.append(env) or (EPIC if env == "epic" else UBISOFT))
    monkeypatch.setattr(exophase, "game_awards", lambda url: asked.append("awards") or [
        {"id": "501", "name": "Explorer", "description": "Look", "icon": "https://m/1.png", "average": 40.0},
        {"id": "502", "name": "Master", "description": "All", "icon": "https://m/2.png", "average": 2.5}])
    monkeypatch.setattr(exophase, "earned", lambda player, master: {"501": T(4)})
    apps = {"Supraland": 813630, "Rainbow Six Siege X": 359550}
    monkeypatch.setattr(steam, "find_app", lambda name: asked.append("find") or ((apps[name], name) if name in apps else None))
    monkeypatch.setattr(steam, "header_pictures", lambda ids: {i: f"https://steam/{i}/header.jpg" for i in ids})
    monkeypatch.setattr(steam, "schema", lambda app_id: asked.append("schema") or (SIEGE if app_id == 359550 else []))
    monkeypatch.setattr(steam, "global_percentages", lambda app_id: {"ACH_1": 60.0, "ACH_2": 3.0, "ACH_3": 0.5})
    monkeypatch.setattr(steamhunters, "game", lambda app_id: {"sh_median_minutes": 600, "sh_players_perfected": 10,
                                                              "sh_players_started": 100})
    return asked


def connect(client):
    r = client.put("/api/videogames/other/account", json={"profile": "https://www.exophase.com/user/SomeGamer/"})
    assert r.status_code == 200, r.text
    return r.json()


def test_epic_and_ubisoft_from_an_exophase_profile(client, exo):
    r = connect(client)
    assert r["profile"] == "SomeGamer" and sorted(r["linked"]) == ["epic", "ubisoft"]
    games = {g["name"]: g for g in r["games"]}
    supra = games["Supraland"]                                     # Epic: the list from Exophase, earned + when
    assert (supra["app_id"], supra["achievements_done"], supra["achievements_total"]) == (f"epic-{supra['game_id']}", 1, 2)
    assert supra["header_url"] == "https://steam/813630/header.jpg" and float(supra["perfect_rate"]) == 10.0
    assert games["Tiny Game"]["completed_at"] and games["Tiny Game"]["playtime_minutes"] == 90   # no page: Exophase's counts
    siege = games["Rainbow Six Siege X"]                           # Ubisoft: Steam's list, nothing ticked yet
    assert (siege["achievements_done"], siege["achievements_total"], siege["challenges_total"]) == (0, 3, 34)
    platforms = {p["platform"]: p for p in r["platforms"]}
    assert (platforms["epic"]["done"], platforms["epic"]["total"], platforms["epic"]["perfect"]) == (6, 7, 1)
    one = client.get(f"/api/videogames/other/{supra['game_id']}").json()
    assert [(a["name"], a["achieved"], bool(a["unlocked_at"])) for a in one["achievements"]] == [
        ("Explorer", True, True), ("Master", False, False)]
    assert client.put("/api/videogames/other/account", json={"profile": "nobody"}).status_code == 422
    assert client.put("/api/videogames/other/account", json={"profile": "bad name!"}).status_code == 422


def test_ticking_off_ubisoft_achievements(client, exo):
    connect(client)
    siege = next(g for g in client.get("/api/videogames/other").json()["games"] if g["platform"] == "ubisoft")
    url = f"/api/videogames/other/{siege['game_id']}"
    r = client.put(f"{url}/achievements", json={"achieved": True}).json()           # tick all...
    assert (r["achievements_done"], r["percent"], bool(r["completed_at"])) == (3, 100, True)
    r = client.put(f"{url}/achievements/ACH_3", json={"achieved": False}).json()    # ...then untick one
    assert (r["achievements_done"], r["achievements_total"]) == (2, 3)
    assert client.put(f"{url}/achievements/NOPE", json={"achieved": True}).status_code == 404
    exo.clear()
    client.put("/api/videogames/other/account", json={"profile": "SomeGamer"})        # a sync keeps the ticks
    assert "schema" not in exo and "find" not in exo                                   # (list fresh, Steam known)
    assert client.get(url).json()["achievements_done"] == 2
    r = client.patch(url, json={"hours": 850}).json()
    assert r["playtime_minutes"] == 51000
    epic = next(g for g in client.get("/api/videogames/other").json()["games"] if g["platform"] == "epic")
    assert client.put(f"/api/videogames/other/{epic['game_id']}/achievements", json={"achieved": True}).status_code == 409


def test_setting_a_games_steam_version(client, exo):
    connect(client)
    siege = next(g for g in client.get("/api/videogames/other").json()["games"] if g["platform"] == "ubisoft")
    url = f"/api/videogames/other/{siege['game_id']}/steam"
    r = client.put(url, json={"link": None}).json()                                 # not the right game: none
    assert (r["steam_app_id"], r["achievements_total"], r["achievements"]) == (None, None, [])
    r = client.put(url, json={"link": "https://store.steampowered.com/app/359550/Rainbow_Six_Siege/"}).json()
    assert (r["steam_app_id"], r["achievements_total"]) == (359550, 3)
    assert client.put(url, json={"link": "not a link"}).status_code == 422


def test_a_ubisoft_game_added_by_hand(client, exo):
    r = client.post("/api/videogames/other", json={"name": "Trackmania", "done": 3, "total": 10, "hours": 2.5})
    assert r.status_code == 201 and (r.json()["platform"], r.json()["playtime_minutes"]) == ("ubisoft", 150)
    assert (r.json()["achievements_done"], r.json()["achievements_total"]) == (3, 10)   # no Steam version: typed in
    assert client.post("/api/videogames/other", json={"name": "Bad", "done": 11, "total": 10}).status_code == 422
    game_id = r.json()["game_id"]
    assert client.patch(f"/api/videogames/other/{game_id}", json={"name": "Trackmania Turbo"}).json()["name"] == "Trackmania Turbo"
    assert client.delete(f"/api/videogames/other/{game_id}").status_code == 204


def test_the_steam_sync_also_reads_the_other_platforms(client, fake, exo):
    connect(client)
    exo.clear()
    setup(client)
    assert "epic" in exo and "uplay" in exo and "awards" not in exo          # lists fresh: not read again
    assert "Epic" in client.get("/api/videogames/account").json()["sync"]["message"]


def test_finding_a_game_on_steam_by_name(monkeypatch):
    import httpx
    monkeypatch.undo()                                                        # the real find_app
    results = {"Rainbow Six Siege X": [], "Rainbow Six Siege": [
        {"type": "app", "id": 4893510, "name": "1,200 Welcome Pack - Rainbow Six Siege"},
        {"type": "app", "id": 359550, "name": "Tom Clancy's Rainbow Six\u00ae Siege"}]}
    monkeypatch.setattr(steam.httpx, "get", lambda url, params, **_k: httpx.Response(200, json={"items": results.get(params["term"], [])}))
    monkeypatch.setattr(steam, "pause", lambda: None)
    assert steam.find_app("Rainbow Six Siege X") == (359550, "Tom Clancy's Rainbow Six\u00ae Siege")   # dropped the X
    assert steam.find_app("Assassin's Creed Unity") is None
    results["Supraland"] = [{"type": "app", "id": 1093730, "name": "Supraland Crash"}, {"type": "app", "id": 813630, "name": "Supraland"}]
    assert steam.find_app("Supraland") == (813630, "Supraland")                 # a one-word name


def test_the_exophase_profile_and_game_readers(monkeypatch):
    import httpx
    assert exophase.profile_name("https://www.exophase.com/user/Some_Gamer/") == "Some_Gamer"
    assert exophase.profile_name("not a name!") is None
    page = ('<li data-endpoint="/steam/user/x/" data-environment="steam" data-playerid="1" class="steam">'
            '<li data-endpoint="/uplay/user/x/" data-environment="uplay" data-playerid="22" class="uplay">'
            '<li data-endpoint="/epic/user/y/" data-environment="epic" data-playerid="11" class="epic">')
    monkeypatch.setattr(exophase, "_get", lambda url, params=None: httpx.Response(200, text=page))
    assert exophase.profile_players("x") == {"uplay": 22, "epic": 11}                  # not Steam (ours already)
    one = {"master_id": 5, "earned_awards": 26, "total_awards": 57, "lastplayed_utc": T(1), "completion_date_utc": 0,
           "resource_tile": "https://m.exophase.com/t.png", "playtimeUnits": {"hours": 2, "minutes": 5},
           "meta": {"master_id": 5, "title": "Tom Clancy\u2019s Game", "endpoint_awards": "https://x/g/#11"}}
    pages = {1: [one], 2: []}
    monkeypatch.setattr(exophase, "_get", lambda url, params=None: httpx.Response(200, json={"success": True,
                                                                                         "games": pages[params["page"]]}))
    games = exophase.player_games(11, "epic")
    assert games == [{"source_id": "5", "name": "Tom Clancy's Game", "picture_url": "https://m.exophase.com/t.png",
                      "page_url": "https://x/g/", "exo_done": 26, "exo_total": 57, "exo_minutes": 125,
                      "last_played": T(1), "exo_completed_at": None}]
