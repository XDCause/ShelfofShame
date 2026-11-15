"""Board games at the table: players kept once, scores and who won, plays timed live, photos, stats
(boardgames_people.py, boardgames_live.py)."""
from datetime import datetime, timedelta, timezone

import pytest

from app import boardgames_live

from .test_boardgames import add_game

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def play(client, game_id, **body):
    r = client.post(f"/api/board-games/{game_id}/plays", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def seat_line(p):
    return [(s["name"], s["score"] and float(s["score"]), s["place"], s["won"]) for s in p["seats"]]


def test_typed_players_become_players_once(client):
    catan = add_game(client)
    play(client, catan["game_id"], players="Sam, Jo and me", winner="sam")
    play(client, catan["game_id"], players="SAM & Alex", winner="Alex")
    r = client.get("/api/board-games/players").json()
    assert sorted(p["name"] for p in r["players"]) == ["Alex", "Jo", "Sam", "me"]       # Sam once, any case
    me = next(p for p in r["players"] if p["name"] == "me")
    client.patch(f"/api/board-games/players/{me['player_id']}", json={"is_me": True, "name": "Me"})
    p = play(client, catan["game_id"], players="Me, Sam")                               # "me" is you from now on
    assert [s["player_id"] for s in p["seats"]][0] == me["player_id"]
    first = client.get("/api/board-games/players").json()["players"][0]
    assert (first["name"], first["is_me"], first["plays"]) == ("Me", True, 2)          # you first in the pickers
    # a winner by first name is the listed player it starts ("Alex" won: Alex Morgan, not a fourth player)
    j = play(client, catan["game_id"], players="Alex Morgan, Robin and Kit", winner="alex")
    assert [(s["name"], s["won"]) for s in j["seats"]] == [("Alex Morgan", True), ("Robin", False), ("Kit", False)]
    together = play(client, catan["game_id"], players="Robin, Kit", winner="Everyone")
    assert [s["won"] for s in together["seats"]] == [True, True]
    assert [s["name"] for s in play(client, catan["game_id"], players="Robin, Kit", winner="Team blue")["seats"]] == ["Robin", "Kit"]
    sam = next(x for x in client.get("/api/board-games/players").json()["players"] if x["name"] == "Sam")
    assert (sam["plays"], sam["wins"], sam["contests"]) == (3, 1, 2)
    # renaming someone rewrites their plays' text
    client.patch(f"/api/board-games/players/{sam['player_id']}", json={"name": "Samantha"})
    assert client.get("/api/board-games/plays").json()[-1]["winner"] == "Samantha"


def test_scores_decide_places_and_the_winner(client):
    catan = add_game(client)
    p = play(client, catan["game_id"], seats=[{"name": "Sam", "score": 8}, {"name": "Jo", "score": 10}, {"name": "Al", "score": 8}])
    assert seat_line(p) == [("Sam", 8, 2, False), ("Jo", 10, 1, True), ("Al", 8, 2, False)]
    assert (p["winner"], p["players"]) == ("Jo", "Sam, Jo, Al")
    tie = play(client, catan["game_id"], seats=[{"name": "Sam", "score": 9}, {"name": "Jo", "score": 9}])
    assert tie["winner"] == "Sam & Jo"                                                   # a tie shares it...
    broken = client.patch(f"/api/board-game-plays/{tie['play_id']}", json={"seats": [
        {"name": "Sam", "score": 9, "won": True}, {"name": "Jo", "score": 9}]}).json()   # ...unless you break it
    assert broken["winner"] == "Sam"
    # the score sheet's parts and the +/- taps add up
    sheet = play(client, catan["game_id"], seats=[{"name": "Sam", "parts": {"Roads": 2, "Cities": 6.5}},
                                                  {"name": "Jo", "adds": [3, 4, -1]}])
    assert seat_line(sheet) == [("Sam", 8.5, 1, True), ("Jo", 6, 2, False)]
    assert client.post(f"/api/board-games/{catan['game_id']}/plays",
                       json={"seats": [{"name": "Sam"}, {"name": "sam"}]}).status_code == 422   # one person twice


def test_lowest_wins_coop_and_no_score(client):
    golf = add_game(client, name="Golf", scoring="lowest")
    p = play(client, golf["game_id"], seats=[{"name": "Sam", "score": 30}, {"name": "Jo", "score": 22}])
    assert p["winner"] == "Jo"
    pandemic = add_game(client, name="Pandemic", scoring="coop")
    won = play(client, pandemic["game_id"], coop_won=True, seats=[{"name": "Sam"}, {"name": "Jo"}])
    assert (won["winner"], [s["won"] for s in won["seats"]]) == ("Everyone", [True, True])
    lost = play(client, pandemic["game_id"], coop_won=False, seats=[{"name": "Sam"}, {"name": "Jo"}])
    assert (lost["winner"], lost["coop_won"]) == (None, False)
    werewolf = add_game(client, name="Werewolf", scoring="none")
    p = play(client, werewolf["game_id"], seats=[{"name": "Sam"}, {"name": "Jo", "won": True}])
    assert (p["winner"], seat_line(p)) == ("Jo", [("Sam", None, None, False), ("Jo", None, 1, True)])
    gave_up = play(client, golf["game_id"], finished=False, seats=[{"name": "Sam", "score": 5}, {"name": "Jo", "score": 9}])
    assert gave_up["winner"] is None and not any(s["won"] for s in gave_up["seats"])
    assert client.patch(f"/api/board-games/{golf['game_id']}", json={"scoring": "most"}).status_code == 422


def test_first_plays_bests_and_records(client):
    catan = add_game(client)
    a = play(client, catan["game_id"], played_on="2026-10-01", seats=[{"name": "Me", "score": 8}, {"name": "Sam", "score": 9}])
    assert [s["first_time"] for s in a["seats"]] == [True, True]
    b = play(client, catan["game_id"], played_on="2026-10-08", seats=[{"name": "Me", "score": 10}, {"name": "Jo", "score": 7}])
    assert [s["first_time"] for s in b["seats"]] == [False, True]
    assert b["highlights"] == ["New record for Catan: Me scored 10 (the best was 9)."]
    c = play(client, catan["game_id"], played_on="2026-10-09", seats=[{"name": "Jo", "score": 8}])
    assert c["highlights"] == ["Jo's best at Catan: 8 (was 7)."]
    stats = client.get(f"/api/board-games/{catan['game_id']}").json()["stats"]
    assert (stats["plays"], float(stats["record"]["score"]), stats["record"]["name"]) == (3, 10, "Me")


def test_plays_keep_where_first_expansions_and_fun(client):
    catan = add_game(client)
    seafarers = add_game(client, name="Catan Seafarers", kind="expansion", base_game_id=catan["game_id"])
    other = add_game(client, name="Wingspan")
    sam = client.post("/api/board-games/players", json={"name": "Sam"}).json()
    p = play(client, catan["game_id"], location="Games Expo", expansions=[seafarers["game_id"]], first_player_id=sam["player_id"],
             fun=5, teach_minutes=15, setup_minutes=10, minutes=60, rounds=7, seats=[{"player_id": sam["player_id"]}])
    assert (p["location"], p["expansion_names"], p["first_player"], p["fun"], p["rounds"]) == \
        ("Games Expo", ["Catan Seafarers"], "Sam", 5, 7)
    assert client.post(f"/api/board-games/{catan['game_id']}/plays", json={"expansions": [other["game_id"]]}).status_code == 422
    assert client.post(f"/api/board-games/{catan['game_id']}/plays", json={"fun": 6}).status_code == 422
    assert client.get("/api/board-games/players").json()["places"] == ["Games Expo"]
    # the calendar counts setup and the teach as time spent on the hobby
    bal = client.get(f"/api/calendar/balance?start={p['played_on']}&end={p['played_on']}").json()
    assert next(b for b in bal if b["hobby"] == "boardgames")["done_minutes"] == 85


@pytest.fixture
def clock(monkeypatch):
    """The live clock, moved by hand."""
    t = {"now": datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(boardgames_live, "now", lambda: t["now"])

    def tick(minutes):
        t["now"] += timedelta(minutes=minutes)
    return tick


def test_a_live_play_times_the_stages_and_becomes_a_play(client, clock):
    catan = add_game(client, score_parts=[" Roads ", "Cities", "", "Roads"])
    assert catan["score_parts"] == ["Roads", "Cities"]
    live = client.post("/api/board-games/live", json={"game_id": catan["game_id"], "location": "Home",
                                                      "seats": [{"name": "Me"}, {"name": "Sam"}]})
    assert live.status_code == 201, live.text
    live = live.json()
    lid = live["live_id"]
    assert (live["stage"], [s["name"] for s in live["seats"]], live["seats"][0]["first_time"]) == ("setup", ["Me", "Sam"], True)
    clock(5)
    client.post(f"/api/board-games/live/{lid}/stage", json={"to": "teach"})
    clock(12)
    client.post(f"/api/board-games/live/{lid}/stage", json={"to": "play"})
    clock(30)
    paused = client.post(f"/api/board-games/live/{lid}/stage", json={"to": "pause"}).json()
    assert (paused["stage"], paused["paused"], paused["seconds"]) == (None, True, {"setup": 300, "teach": 720, "play": 1800})
    clock(20)                                                          # a break: not counted
    resumed = client.post(f"/api/board-games/live/{lid}/stage", json={"to": "resume"}).json()
    assert (resumed["stage"], resumed["seconds"]["play"]) == ("play", 1800)
    me, sam = (s["player_id"] for s in live["seats"])
    scored = client.patch(f"/api/board-games/live/{lid}", json={"first_player_id": sam, "rounds": 4, "seats": [
        {"player_id": me, "adds": [1, 2, 1]}, {"player_id": sam, "parts": {"Roads": 2, "Cities": 4}}]}).json()
    assert [float(s["total"]) for s in scored["seats"]] == [4, 6]
    photo = client.post(f"/api/board-games/live/{lid}/photos", content=PNG, headers={"Content-Type": "image/png"})
    assert photo.status_code == 201
    assert [g["live_id"] for g in client.get("/api/board-games/live").json()] == [lid]
    assert client.get("/api/board-games/summary").json()["live"][0]["game_name"] == "Catan"
    clock(30)
    done = client.post(f"/api/board-games/live/{lid}/finish", json={"fun": 4, "notes": "Close one"})
    assert done.status_code == 201, done.text
    p = done.json()["play"]
    assert (p["setup_minutes"], p["teach_minutes"], p["minutes"], p["winner"], p["first_player"], p["rounds"], p["fun"]) == \
        (5, 12, 60, "Sam", "Sam", 4, 4)
    assert (p["location"], p["played_on"], len(p["photos"])) == ("Home", "2026-11-15", 1)
    assert client.get(p["photos"][0]["url"]).content == PNG
    assert client.get("/api/board-games/live").json() == []
    assert client.get(f"/api/board-games/live/{lid}").status_code == 404


def test_a_live_play_of_a_friends_game_and_throwing_one_away(client, clock):
    live = client.post("/api/board-games/live", json={"game_name": "Ark Nova", "stage": "teach"}).json()
    assert (live["game_status"], live["stage"]) == ("Played elsewhere", "teach")
    assert client.post("/api/board-games/live", json={}).status_code == 422
    assert client.delete(f"/api/board-games/live/{live['live_id']}").status_code == 204
    pandemic = add_game(client, name="Pandemic", scoring="coop")
    live = client.post("/api/board-games/live", json={"game_id": pandemic["game_id"], "seats": [{"name": "Jo"}]}).json()
    p = client.post(f"/api/board-games/live/{live['live_id']}/finish", json={"coop_won": True}).json()["play"]
    assert (p["winner"], p["minutes"], p["setup_minutes"]) == ("Everyone", None, 0)          # never got past setup


def test_merging_deleting_and_groups(client):
    catan = add_game(client)
    play(client, catan["game_id"], players="Sam, Jo")
    play(client, catan["game_id"], players="Samm", winner="Samm")
    people = {p["name"]: p["player_id"] for p in client.get("/api/board-games/players").json()["players"]}
    group = client.post("/api/board-games/groups", json={"name": "Thursday crew", "player_ids": [people["Samm"], people["Jo"]]}).json()
    assert client.delete(f"/api/board-games/players/{people['Samm']}").status_code == 409      # in a play: merge instead
    assert client.post(f"/api/board-games/players/{people['Jo']}/merge", json={"into": people["Sam"]}).status_code == 409   # played together
    merged = client.post(f"/api/board-games/players/{people['Samm']}/merge", json={"into": people["Sam"]}).json()
    assert (merged["plays"], merged["wins"]) == (2, 1)
    assert client.get("/api/board-games/plays").json()[0]["winner"] == "Sam"
    g = client.get("/api/board-games/players").json()["groups"][0]
    assert (g["group_id"], sorted(g["player_ids"])) == (group["group_id"], sorted([people["Sam"], people["Jo"]]))
    new = client.post("/api/board-games/players", json={"name": "Kim"}).json()
    assert client.post("/api/board-games/players", json={"name": "kim"}).status_code == 409
    assert client.delete(f"/api/board-games/players/{new['player_id']}").status_code == 204
    assert client.post("/api/board-games/groups", json={"name": "X", "player_ids": [999]}).status_code == 422
    assert client.delete(f"/api/board-games/groups/{group['group_id']}").status_code == 204


def test_stats_you_against_everyone(client):
    catan = add_game(client)
    me = client.post("/api/board-games/players", json={"name": "Me", "is_me": True}).json()
    for mine, sams in ((10, 8), (7, 9), (12, 3)):
        play(client, catan["game_id"], minutes=50, teach_minutes=10,
             seats=[{"player_id": me["player_id"], "score": mine}, {"name": "Sam", "score": sams}])
    s = client.get("/api/board-games/stats").json()
    sam = next(p for p in s["players"] if p["name"] == "Sam")
    assert sam["vs_me"] == {"player_id": sam["player_id"], "together": 3, "i_beat": 2, "they_beat": 1, "coop_plays": 0, "coop_wins": 0}
    g = s["games"][0]
    assert (g["name"], g["my_plays"], g["my_wins"], float(g["my_best"]), g["avg_teach"], g["avg_minutes"]) == ("Catan", 3, 2, 12, 10, 50)
    assert s["has_me"] and s["times"]["teach"] == 30


def test_play_photos(client):
    catan = add_game(client)
    p = play(client, catan["game_id"])
    r = client.post(f"/api/board-game-plays/{p['play_id']}/photos?caption=Final%20board", content=PNG,
                    headers={"Content-Type": "image/png"})
    assert r.status_code == 201 and r.json()["caption"] == "Final board"
    assert client.get("/api/board-games/plays").json()[0]["photos"][0]["caption"] == "Final board"
    assert client.post(f"/api/board-game-plays/{p['play_id']}/photos", content=b"x", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.delete(f"/api/board-games/play-photos/{r.json()['photo_id']}").status_code == 204
    assert client.get("/api/board-games/plays").json()[0]["photos"] == []


def test_h_index_streaks_and_going_first():
    from app.boardgames_people import first_player_stats, h_index, plays_to_next, win_streaks
    assert h_index([]) == 0 and h_index([1]) == 1 and h_index([5, 4, 3, 1]) == 3 and h_index([2, 2, 2, 2]) == 2
    assert plays_to_next([5, 4, 3, 1]) == 4        # the top 4 games each need 4 plays: 0 + 0 + 1 + 3
    assert win_streaks([]) == {"current": 0, "longest": 0}
    assert win_streaks([True, True, False, True]) == {"current": 1, "longest": 2}
    assert win_streaks([False, True, True, True]) == {"current": 3, "longest": 3}
    rows = [{"game_id": 1, "name": "A", "won": w, "seats": 4} for w in (True, False, False)]
    rows.append({"game_id": 2, "name": "B", "won": True, "seats": 2})
    f = first_player_stats(rows)
    assert (f["plays"], f["wins"], f["rate"]) == (4, 2, 50)
    assert [(g["name"], g["rate"], g["chance"]) for g in f["games"]] == [("A", 33, 25)]   # B has fewer than 3


def test_stats_h_index_streaks_and_first_player(client):
    me = client.post("/api/board-games/players", json={"name": "Me", "is_me": True}).json()
    sam = client.post("/api/board-games/players", json={"name": "Sam"}).json()
    catan = add_game(client)
    for day, mine, sams in (("2026-10-01", 5, 9), ("2026-10-02", 9, 5), ("2026-10-03", 9, 5), ("2026-10-04", 9, 5)):
        play(client, catan["game_id"], played_on=day, first_player_id=me["player_id"],
             seats=[{"player_id": me["player_id"], "score": mine}, {"player_id": sam["player_id"], "score": sams}])
    s = client.get("/api/board-games/stats").json()
    assert (s["h_index"]["n"], s["h_index"]["plays_to_next"], [g["name"] for g in s["h_index"]["games"]]) == (1, 2, ["Catan"])
    mine = next(p for p in s["players"] if p["is_me"])
    theirs = next(p for p in s["players"] if p["name"] == "Sam")
    assert mine["streak"] == {"current": 3, "longest": 3} and theirs["streak"] == {"current": 0, "longest": 1}
    f = s["first_player"]
    assert (f["plays"], f["wins"], f["rate"], f["chance"]) == (4, 3, 75, 50)
    assert f["games"][0]["name"] == "Catan"
