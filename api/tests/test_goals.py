"""Goals: details, to-dos, a number to track (or one counted from the hobbies), pace, habits, goals inside bigger
goals, nudges, progress notes and the activity feed."""
from datetime import timedelta
from pathlib import Path

from app import goal_sources
from app.db import db


def D(days=0):
    """A day from today - the database's today (Brisbane), as the app's; this container runs on UTC."""
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
    return today + timedelta(days=days)


def test_goal_with_todos_and_progress(client):
    goal = client.post("/api/goals", json={
        "title": " Finish the shelf of shame ", "hobby": "models", "why": "Too many boxes.", "details": "One kit a month.",
        "target_date": "2027-06-30", "steps": ["Finish the Zero", " ", "Finish the Sherman", "Finish the P-40E"]}).json()
    assert goal["title"] == "Finish the shelf of shame" and goal["status"] == "active"
    assert [t["title"] for t in goal["todos"]] == ["Finish the Zero", "Finish the Sherman", "Finish the P-40E"]   # in order
    assert all(t["goal_id"] == goal["goal_id"] and t["hobby"] == "models" for t in goal["todos"])
    assert (goal["progress"], goal["next_step"]) == (0, "Finish the Zero")
    zero = goal["todos"][0]["todo_id"]
    client.post(f"/api/todos/{zero}/done")
    g = client.get(f"/api/goals/{goal['goal_id']}").json()
    assert (g["todos_done"], g["todos_total"]) == (1, 3) and abs(g["progress"] - 1 / 3) < 1e-9 and g["next_step"] == "Finish the Sherman"
    assert g["todos"][-1]["todo_id"] == zero                                 # ticked ones after the open ones
    # A to-do added for it (Goals > To-do, Home) counts too.
    client.post("/api/todos", json={"title": "Buy decal softener", "goal_id": goal["goal_id"]})
    assert client.get(f"/api/goals/{goal['goal_id']}").json()["todos_total"] == 4
    assert client.post("/api/goals", json={"title": "X", "hobby": "knitting"}).status_code == 422
    assert client.post("/api/goals", json={"title": " "}).status_code == 422
    # Deleting the goal leaves its to-dos on the list.
    assert client.delete(f"/api/goals/{goal['goal_id']}").status_code == 204
    assert {t["title"] for t in client.get("/api/todos").json()} >= {"Finish the Sherman", "Buy decal softener"}


def test_number_goal_and_notes(client):
    goal = client.post("/api/goals", json={"title": "Read 30 books", "hobby": "reading", "unit": "books",
                                           "start_value": 0, "target_value": 30}).json()
    assert goal["progress"] is None                        # no current value yet, no to-dos
    gid = goal["goal_id"]
    g = client.post(f"/api/goals/{gid}/updates", json={"day": "2026-10-01", "value": 6, "text": "Good month"}).json()
    assert g["current_value"] == 6 and abs(g["progress"] - 0.2) < 1e-9
    g = client.post(f"/api/goals/{gid}/updates", json={"day": "2026-09-01", "value": 3}).json()
    assert g["current_value"] == 6                         # an older note doesn't move it back
    g = client.post(f"/api/goals/{gid}/updates", json={"day": "2026-10-10", "text": "Halfway through Dune"}).json()
    assert [u["day"] for u in g["updates"]] == ["2026-10-10", "2026-10-01", "2026-09-01"]
    assert [v for _, v in g["series"]] == [0, 3, 6]        # the chart: the start, then each note's number in order
    assert client.post(f"/api/goals/{gid}/updates", json={"text": "  "}).status_code == 422
    newest = g["updates"][1]["update_id"]
    g = client.delete(f"/api/goal-updates/{newest}").json()
    assert g["current_value"] == 3                         # back to the latest one left
    # Past the target counts as all the way.
    assert client.patch(f"/api/goals/{gid}", json={"current_value": 45}).json()["progress"] == 1
    # Going down (lose 5 kg: 80 -> 75): halfway at 77.5.
    kg = client.post("/api/goals", json={"title": "Lose 5 kg", "unit": "kg", "start_value": 80, "target_value": 75,
                                         "current_value": 77.5}).json()
    assert kg["progress"] == 0.5


def test_status_and_order_and_activity(client):
    a = client.post("/api/goals", json={"title": "Later", "target_date": "2027-12-01"}).json()
    b = client.post("/api/goals", json={"title": "Sooner", "target_date": "2027-01-01"}).json()
    c = client.post("/api/goals", json={"title": "Pinned one", "pinned": True}).json()
    done = client.patch(f"/api/goals/{a['goal_id']}", json={"status": "done"}).json()
    assert done["done_on"] is not None and done["days_left"] is None
    listed = client.get("/api/goals").json()
    assert [g["title"] for g in listed["goals"]] == ["Pinned one", "Sooner", "Later"]
    assert listed["counts"] == {"active": 2, "paused": 0, "done": 1, "dropped": 0, "upcoming": 0}
    assert [g["title"] for g in client.get("/api/goals?status=done").json()["goals"]] == ["Later"]
    client.post(f"/api/goals/{b['goal_id']}/updates", json={"text": "Booked lessons"})
    feed = client.get("/api/activity?limit=50").json()
    assert {(r["verb"], r["title"]) for r in feed if r["kind"] == "goal"} == {("Reached", "Later"), ("Progress on", "Sooner")}
    back = client.patch(f"/api/goals/{a['goal_id']}", json={"status": "active"}).json()
    assert back["done_on"] is None
    assert client.delete(f"/api/goals/{c['goal_id']}").status_code == 204
    assert client.get(f"/api/goals/{c['goal_id']}").status_code == 404


def test_year_and_three_year_goals(client):
    this_year = client.get("/api/goals").json()["this_year"]
    year = client.post("/api/goals", json={"title": "Read 30 books", "timeframe": "year"}).json()
    assert (year["period_start"], year["target_date"]) == (this_year, f"{this_year}-12-31")
    three = client.post("/api/goals", json={"title": "Build a car", "timeframe": "three_years", "period_start": 2027}).json()
    assert three["target_date"] == "2029-12-31"
    # Moving it to next year moves the target day along; a day you picked yourself stays.
    moved = client.patch(f"/api/goals/{year['goal_id']}", json={"period_start": this_year + 1}).json()
    assert moved["target_date"] == f"{this_year + 1}-12-31"
    client.patch(f"/api/goals/{three['goal_id']}", json={"target_date": "2028-06-30"})
    kept = client.patch(f"/api/goals/{three['goal_id']}", json={"timeframe": "year"}).json()
    assert (kept["timeframe"], kept["period_start"], kept["target_date"]) == ("year", 2027, "2028-06-30")
    plain = client.patch(f"/api/goals/{three['goal_id']}", json={"timeframe": None}).json()
    assert (plain["timeframe"], plain["period_start"]) == (None, None)
    assert client.post("/api/goals", json={"title": "X", "timeframe": "decade"}).status_code == 422
    assert client.post("/api/goals", json={"title": "No time", "target_date": None}).json()["target_date"] is None


def test_every_source_counts_without_error(client):
    """Each source's query runs against a fresh database (a wrong column name would only show up here)."""
    assert {s["key"] for s in client.get("/api/goals/sources").json()} == set(goal_sources.SOURCES)
    with db() as conn:
        for key in goal_sources.SOURCES:
            m = goal_sources.measure(conn, key, D(-365), D(0))
            assert m["current"] in (0, None), key
    assert client.post("/api/goals", json={"title": "X", "source": "vibes"}).status_code == 422


def test_a_goal_that_counts_books_by_itself(client):
    year = D(0).year
    with db() as conn:
        for title, day in [("Dune", f"{year - 1}-12-20"), ("Emma", f"{year}-01-05"), ("Ulysses", D(0).isoformat())]:
            conn.execute("INSERT INTO books (title, status, finished_on) VALUES (%s, 'finished', %s)", (title, day))
        conn.execute("INSERT INTO books (title, status) VALUES ('Reading now', 'reading')")
    g = client.post("/api/goals", json={"title": "Read 24 books", "timeframe": "year", "source": "books_finished",
                                        "target_value": 24}).json()
    assert (g["unit"], g["hobby"], g["source_label"]) == ("books", "reading", "Books finished")
    assert (g["start_value"], g["current_value"]) == (0, 2)            # this year's two, not last year's
    assert g["series"][0][1] == 0 and g["series"][-1][1] == 2 and g["last_moved"] == D(0).isoformat()
    assert client.patch(f"/api/goals/{g['goal_id']}", json={"current_value": 20}).json()["current_value"] == 2   # counted, not typed
    off = client.patch(f"/api/goals/{g['goal_id']}", json={"source": None, "current_value": 5}).json()
    assert (off["source"], off["current_value"]) == (None, 5)          # back to a number you give


def test_a_rating_goal_starts_where_you_were(client):
    """A chess.com rating: its rated games in exact order (several on one day), then chess.com's own latest - the
    Chess tab's number. Club games are another rating, counted only by club_rating."""
    import json
    with db() as conn:
        for at, rating in [(D(-40), 1150), (D(-10), 1190)]:
            conn.execute("""INSERT INTO chess_games (source, played_at, time_class, rated, rules, colour, my_rating, opp_name, result)
                            VALUES ('chesscom', %s, 'rapid', true, 'chess', 'white', %s, 'X', 'win')""", (at, rating))
        for hour, rating in [(20, 1236), (9, 1260), (14, 1248)]:      # the same day: the 8 pm one is the latest
            conn.execute("""INSERT INTO chess_games (source, played_at, time_class, rated, rules, colour, my_rating, opp_name, result)
                            VALUES ('chesscom', %s::date + make_interval(hours => %s), 'rapid', true, 'chess', 'black', %s, 'Y', 'win')""",
                         (D(-3), hour, rating))
        conn.execute("""INSERT INTO chess_games (source, played_at, time_class, rated, colour, my_rating, opp_name, result)
                        VALUES ('otb', %s, 'rapid', true, 'white', 1500, 'Club', 'win')""", (D(-1),))
    g = client.post("/api/goals", json={"title": "Reach 1400", "source": "chess_rapid", "target_value": 1400,
                                        "started_on": D(-20).isoformat()}).json()
    assert (g["start_value"], g["current_value"]) == (1150, 1236)      # the rating when it began, and the last game's
    assert [v for _, v in g["history"]] == [1150, 1190, 1236]         # its whole story, a point a day (that day's last)
    assert "history" not in client.get("/api/goals").json()["goals"][0]   # (only a goal's own page draws it)
    assert abs(g["progress"] - 86 / 250) < 1e-9
    with db() as conn:                                                 # chess.com says 1241 now: that's where you are
        stats = {"chess_rapid": {"last": {"rating": 1241, "date": int(conn.execute("SELECT extract(epoch FROM now())::bigint AS t").fetchone()["t"])}}}
        conn.execute("INSERT INTO chess_account (id, username, stats) VALUES (1, 'someone', %s) "
                     "ON CONFLICT (id) DO UPDATE SET stats = EXCLUDED.stats", (json.dumps(stats),))
    assert client.get(f"/api/goals/{g['goal_id']}").json()["current_value"] == 1241
    club = client.post("/api/goals", json={"title": "Club 1600", "source": "club_rating", "target_value": 1600}).json()
    assert club["current_value"] == 1500 and club["source_latest"] == D(-1).isoformat()


def test_pace_ahead_on_track_behind(client):
    def goal(now):
        return client.post("/api/goals", json={"title": f"At {now}", "started_on": D(-50).isoformat(), "target_date": D(50).isoformat(),
                                               "unit": "km", "start_value": 0, "target_value": 100, "current_value": now}).json()
    behind, even, ahead = goal(20), goal(50), goal(80)
    assert (behind["pace"]["status"], even["pace"]["status"], ahead["pace"]["status"]) == ("behind", "on_track", "ahead")
    assert behind["pace"]["expected"] == 50 and abs(behind["pace"]["per_month"] - 80 / (50 / 30.44)) < 0.01
    assert client.patch(f"/api/goals/{even['goal_id']}", json={"current_value": 100}).json()["pace"]["status"] == "done"
    assert client.patch(f"/api/goals/{even['goal_id']}", json={"status": "paused"}).json()["pace"] is None


def test_a_habit_counts_its_weeks(client):
    g = client.post("/api/goals", json={"title": "Draw twice a week", "kind": "habit", "habit_times": 2}).json()
    assert (g["habit_every"], g["habit"]["this"], g["habit"]["met"]) == ("week", 0, False)
    g = client.post(f"/api/goals/{g['goal_id']}/updates", json={}).json()           # "Did it": no words needed
    assert g["habit"]["this"] == 1 and g["updates"][0]["text"] == "Did it" and g["progress"] == 0.5
    g = client.post(f"/api/goals/{g['goal_id']}/updates", json={"text": "Sketched the Sherman"}).json()
    assert (g["habit"]["this"], g["habit"]["met"], g["habit"]["streak"], g["habit"]["left"]) == (2, True, 1, 0)
    # One counted from the hobby: chess games in a month.
    with db() as conn:
        for _ in range(3):
            conn.execute("""INSERT INTO chess_games (source, played_at, time_class, rated, colour, opp_name, result)
                            VALUES ('otb', now(), 'rapid', false, 'black', 'Y', 'draw')""")
    c = client.post("/api/goals", json={"title": "Play chess", "kind": "habit", "habit_times": 8, "habit_every": "month",
                                        "source": "chess_games"}).json()
    assert (c["habit"]["this"], c["habit"]["left"], c["habit"]["every"]) == (3, 5, "month")


def test_goals_inside_a_bigger_goal(client):
    big = client.post("/api/goals", json={"title": "Get fitter", "timeframe": "three_years"}).json()
    hike = client.post("/api/goals", json={"title": "Hike 300 km", "timeframe": "year", "parent_id": big["goal_id"],
                                           "unit": "km", "start_value": 0, "target_value": 300, "current_value": 150}).json()
    assert (hike["parent_id"], hike["parent_title"]) == (big["goal_id"], "Get fitter")
    client.post("/api/goals", json={"title": "Swim", "parent_id": big["goal_id"], "steps": ["Join a pool"]})
    g = client.get(f"/api/goals/{big['goal_id']}").json()
    assert [k["title"] for k in g["goals"]] == ["Hike 300 km", "Swim"]
    assert abs(g["progress"] - (0.5 + 0) / 2) < 1e-9 and g["progress_from"] == "goals"   # nothing of its own: theirs
    assert client.patch(f"/api/goals/{big['goal_id']}", json={"parent_id": big["goal_id"]}).status_code == 422
    assert client.patch(f"/api/goals/{big['goal_id']}", json={"parent_id": hike["goal_id"]}).status_code == 422
    other = client.post("/api/goals", json={"title": "Y"}).json()
    assert client.patch(f"/api/goals/{other['goal_id']}", json={"parent_id": hike["goal_id"]}).status_code == 422   # one level
    assert client.patch(f"/api/goals/{other['goal_id']}", json={"parent_id": 999999}).status_code == 422
    client.delete(f"/api/goals/{big['goal_id']}")
    assert client.get(f"/api/goals/{hike['goal_id']}").json()["parent_id"] is None       # the bigger goal gone: this one stays


def test_nudges_and_the_monthly_check_in(client):
    g = client.post("/api/goals", json={"title": "Quiet one", "started_on": D(-30).isoformat()}).json()
    client.post("/api/goals", json={"title": "New one"})
    n = client.get("/api/goals/nudges").json()
    assert [(s["title"], s["days"]) for s in n["stale"]] == [("Quiet one", 30)]
    assert n["checkin"] == (D(0).day <= 7)                    # the first week of a month, no notes yet
    client.post(f"/api/goals/{g['goal_id']}/updates", json={"text": "Back on it"})
    n = client.get("/api/goals/nudges").json()
    assert n["stale"] == [] and n["checkin"] is False         # a note this month: moved, and checked in
    assert client.post("/api/goals/checkin-seen").status_code == 204


def test_steps_become_to_dos_once(client):
    """83_goal_tracking.sql copies each old step to a to-do under its goal - and running it again copies nothing."""
    g = client.post("/api/goals", json={"title": "Old goal", "hobby": "models"}).json()
    with db() as conn:
        conn.execute("INSERT INTO goal_steps (goal_id, text, sort_order) VALUES (%s, 'Second', 1), (%s, 'First', 0)", (g["goal_id"],) * 2)
        conn.execute("INSERT INTO goal_steps (goal_id, text, sort_order, done, done_on) VALUES (%s, 'Done one', 2, true, %s)",
                     (g["goal_id"], D(-3)))
        migration = (Path(__file__).parents[2] / "db" / "init" / "83_goal_tracking.sql").read_text()
        conn.execute(migration)
        conn.execute(migration)
    todos = client.get(f"/api/goals/{g['goal_id']}").json()["todos"]
    assert [(t["title"], t["done_at"] is not None) for t in todos] == [("First", False), ("Second", False), ("Done one", True)]
    assert all(t["hobby"] == "models" for t in todos)


def test_a_goal_whose_time_has_not_begun_is_upcoming(client):
    """A next-year goal: upcoming (not active yet) - no pace, no nudge, counted apart, and not dragging a bigger goal down."""
    next_year = D(0).year + 1
    big = client.post("/api/goals", json={"title": "Triathlon", "timeframe": "three_years"}).json()
    now = client.post("/api/goals", json={"title": "Swim 1 km", "timeframe": "year", "parent_id": big["goal_id"], "unit": "m",
                                          "start_value": 0, "target_value": 1000, "current_value": 500}).json()
    later = client.post("/api/goals", json={"title": "Sprint race", "timeframe": "year", "period_start": next_year,
                                            "parent_id": big["goal_id"], "started_on": D(-30).isoformat(),
                                            "unit": "races", "start_value": 0, "target_value": 1, "current_value": 0}).json()
    assert (now["upcoming"], later["upcoming"]) == (False, True)
    assert later["pace"] is None and later["start_day"] == f"{next_year}-01-01" and now["pace"] is not None
    assert client.get("/api/goals").json()["counts"]["upcoming"] == 1
    assert "Sprint race" not in [s["title"] for s in client.get("/api/goals/nudges").json()["stale"]]
    g = client.get(f"/api/goals/{big['goal_id']}").json()
    assert abs(g["progress"] - 0.5) < 1e-9                           # only this year's goal counts yet
    assert [(k["title"], k["upcoming"]) for k in g["goals"]] == [("Swim 1 km", False), ("Sprint race", True)]


def test_a_yes_or_no_goal(client):
    """A milestone (proposed, yes or no): no number, no pace - not "Behind" - and no nudge unless it has steps."""
    g = client.post("/api/goals", json={"title": "Propose", "kind": "milestone", "timeframe": "three_years",
                                        "started_on": D(-60).isoformat(), "target_value": 5}).json()
    assert (g["kind"], g["progress"], g["pace"]) == ("milestone", None, None)
    assert "Propose" not in [s["title"] for s in client.get("/api/goals/nudges").json()["stale"]]
    t = client.post("/api/todos", json={"title": "Buy the ring", "goal_id": g["goal_id"]}).json()
    client.post("/api/todos", json={"title": "Plan the day", "goal_id": g["goal_id"]})
    client.post(f"/api/todos/{t['todo_id']}/done")
    g = client.get(f"/api/goals/{g['goal_id']}").json()
    assert (g["progress"], g["pace"]) == (0.5, None)                   # its steps show, still no pace
    assert client.patch(f"/api/goals/{g['goal_id']}", json={"status": "done"}).json()["progress"] == 1

