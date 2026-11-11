"""Sudoku: saving puzzles (checked: a valid answer that agrees with the clues and is the only one), playing, solving
(checked against the answer), the daily puzzle, summary, stats, and the parts other pages show."""
from app import sudoku

# Wikipedia's example puzzle and its answer.
PUZZLE = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
SOLUTION = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"


def game(client, **extra):
    r = client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": SOLUTION, "difficulty": "Easy",
                                               "techniques": {"hidden_single": 30, "naked_single": 21}, "hardest": "naked_single", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def state(v, notes=None):
    return {"v": v, "n": notes or [0] * 81}


def test_solve_count_and_checks():
    grid = [int(x) for x in PUZZLE]
    assert sudoku.solve_count(grid) == 1
    two = [0] * 18 + [int(x) for x in SOLUTION[18:]]       # rows 1 and 2 blank: they can swap
    assert sudoku.solve_count(two) == 2
    assert sudoku.solve_count([5, 5] + [0] * 79) == 0       # a clash: no answer


def test_a_puzzle_is_checked(client):
    bad = SOLUTION[:80] + ("1" if SOLUTION[80] != "1" else "2")
    assert "valid finished grid" in client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": bad, "difficulty": "Easy"}).json()["detail"]
    clash = "6" + SOLUTION[1:]
    assert client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": clash, "difficulty": "Easy"}).status_code == 422
    two = "0" * 18 + SOLUTION[18:]
    r = client.post("/api/sudoku/games", json={"puzzle": two, "solution": SOLUTION, "difficulty": "Easy", "source": "typed"})
    assert r.status_code == 422 and "more than one answer" in r.json()["detail"]
    few = SOLUTION[0] + "0" * 80
    assert "17 clues" in client.post("/api/sudoku/games", json={"puzzle": few, "solution": SOLUTION, "difficulty": "Easy"}).json()["detail"]
    assert client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": SOLUTION, "difficulty": "Easy", "source": "daily"}).status_code == 422


def test_play_save_solve(client):
    g = game(client)
    assert g["clues"] == 30 and g["status"] == "playing" and g["techniques"]["hidden_single"] == 30
    half = SOLUTION[:40] + PUZZLE[40:]
    notes = [0] * 81
    notes[45] = 0b11                                         # 1 and 2 noted in r6c1
    r = client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": state(half, notes), "seconds": 120, "mistakes": 1,
                                                               "hints": 2, "hint_kinds": {"hidden_single": 2}})
    assert r.status_code == 200 and r.json()["state"]["n"][45] == 3 and r.json()["seconds"] == 120
    listed = client.get("/api/sudoku/games?status=playing").json()
    assert listed[0]["filled"] == 40 + sum(1 for c in PUZZLE[40:] if c != "0") and "solution" not in listed[0]
    wrong = "0" + PUZZLE[1:]
    assert "clues" in client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": state(wrong)}).json()["detail"]
    assert client.patch(f"/api/sudoku/games/{g['game_id']}", json={"status": "solved"}).status_code == 422     # not the answer yet
    r = client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": state(SOLUTION), "seconds": 300, "status": "solved"}).json()
    assert r["status"] == "solved" and r["finished_at"]
    assert client.patch(f"/api/sudoku/games/{g['game_id']}", json={"seconds": 999}).status_code == 409       # finished
    feed = client.get("/api/activity").json()
    assert any(x["kind"] == "sudoku" and x["title"] == "Easy sudoku" and x["detail"] == "5 min 0 s · 2 hints" for x in feed)


def test_give_up_and_delete(client):
    g = game(client)
    r = client.patch(f"/api/sudoku/games/{g['game_id']}", json={"status": "gave_up"}).json()
    assert r["status"] == "gave_up" and r["finished_at"]
    assert client.delete(f"/api/sudoku/games/{g['game_id']}").status_code == 204
    assert client.get(f"/api/sudoku/games/{g['game_id']}").status_code == 404


def test_daily_once_a_day(client):
    assert client.get("/api/sudoku/daily").json() is None
    a = game(client, source="daily", daily_on="2026-11-11")
    b = game(client, source="daily", daily_on="2026-11-11")
    assert a["game_id"] == b["game_id"]
    assert client.get("/api/sudoku/daily?day=2026-11-11").json()["game_id"] == a["game_id"]


def test_an_offline_game_arrives_with_its_progress(client):
    g = game(client, state=state(SOLUTION[:20] + PUZZLE[20:]), seconds=95, hints=1)
    assert (g["seconds"], g["hints"], g["state"]["v"][:20]) == (95, 1, SOLUTION[:20])


def test_summary_stats_goals(client):
    today = client.get("/api/sudoku/summary").json()["today"]
    d = game(client, source="daily", daily_on=today, difficulty="Hard")
    client.patch(f"/api/sudoku/games/{d['game_id']}", json={"state": state(SOLUTION), "seconds": 600, "status": "solved"})
    e = game(client)
    client.patch(f"/api/sudoku/games/{e['game_id']}", json={"state": state(SOLUTION), "seconds": 200, "status": "solved", "hints": 1,
                                                          "hint_kinds": {"x_wing": 1}})
    game(client, difficulty="Expert")                         # still playing
    s = client.get("/api/sudoku/summary").json()
    assert (s["solved"], s["playing_count"], s["streak"]["current"], s["daily_streak"]["current"]) == (2, 1, 1, 1)
    assert s["daily"]["status"] == "solved" and s["playing"]["difficulty"] == "Expert"
    st = client.get("/api/sudoku/stats").json()
    per = {p["difficulty"]: p for p in st["per_difficulty"]}
    assert (per["Easy"]["solved"], per["Easy"]["best"], per["Easy"]["clean"]) == (1, 200, 0)
    assert per["Hard"]["clean"] == 1 and per["Expert"]["solved"] == 0
    assert st["hints_by_technique"] == {"x_wing": 1} and st["techniques_needed"]["hidden_single"] == 2
    assert st["totals"]["dailies"] == 1 and st["by_day"][0]["count"] == 2
    goal = client.post("/api/goals", json={"title": "Solve 50", "timeframe": "year", "source": "sudokus_solved", "target_value": 50}).json()
    assert goal["current_value"] == 2
    assert client.post("/api/calendar/parse", json={"text": "Sudoku club Thu 7pm"}).json()["hobby"] == "sudoku"


# A 16 x 16: the pattern grid (4 x 4 boxes; digits 1-9 then A-G), with one cell of each row blank - so one answer.
SYM = "0123456789ABCDEFG"
GIANT_ANSWER = "".join(SYM[(4 * (r % 4) + r // 4 + c) % 16 + 1] for r in range(16) for c in range(16))
GIANT = "".join("0" if c == r else GIANT_ANSWER[r * 16 + c] for r in range(16) for c in range(16))


def test_a_16_by_16(client):
    assert sudoku.solve_count([SYM.index(x) for x in GIANT]) == 1
    r = client.post("/api/sudoku/games", json={"puzzle": GIANT, "solution": GIANT_ANSWER, "size": 16, "difficulty": "Easy"})
    assert r.status_code == 201, r.text
    g = r.json()
    assert (g["size"], g["clues"]) == (16, 240)
    assert client.post("/api/sudoku/games", json={"puzzle": GIANT, "solution": GIANT_ANSWER, "size": 9, "difficulty": "Easy"}).status_code == 422
    assert client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": state(PUZZLE)}).status_code == 422   # a 9 x 9 board
    done = client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": {"v": GIANT_ANSWER, "n": [0] * 256}, "seconds": 400, "status": "solved"}).json()
    assert done["status"] == "solved" and "giant" in {a["key"] for a in done["new_awards"]}
    st = client.get("/api/sudoku/stats").json()
    assert st["giant"][0]["solved"] == 1 and st["per_difficulty"][0]["solved"] == 0 and st["totals"]["giants"] == 1
    assert any(x["title"] == "Easy 16×16 sudoku" for x in client.get("/api/activity").json())
    assert client.post("/api/sudoku/games", json={"puzzle": GIANT, "solution": GIANT_ANSWER, "size": 16, "difficulty": "Easy",
                                                  "source": "daily", "daily_on": "2026-11-11"}).status_code == 422


def test_achievements(client):
    before = {a["key"]: a for a in client.get("/api/sudoku/achievements").json()}
    assert not any(a["unlocked_at"] for a in before.values()) and before["solved_10"]["target"] == 10
    g = game(client, source="typed", difficulty="Hard")
    done = client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": state(SOLUTION), "seconds": 240, "status": "solved"}).json()
    new = {a["key"] for a in done["new_awards"]}
    assert {"first", "clean", "typed", "medium", "hard", "clean_hard", "fast_hard"} <= new and "expert" not in new
    e = game(client, difficulty="Expert", hints=2)
    again = client.patch(f"/api/sudoku/games/{e['game_id']}", json={"state": state(SOLUTION), "seconds": 4000, "status": "solved"}).json()
    assert {a["key"] for a in again["new_awards"]} >= {"expert", "long_haul"} and "first" not in {a["key"] for a in again["new_awards"]}
    now = {a["key"]: a for a in client.get("/api/sudoku/achievements").json()}
    assert now["first"]["game_id"] == g["game_id"] and now["solved_10"]["progress"] == 2 and not now["solved_10"]["unlocked_at"]
    assert now["all_levels"]["progress"] == 2
    assert client.get("/api/sudoku/summary").json()["awards"]["earned"] == sum(1 for a in now.values() if a["unlocked_at"])


def test_weekly_sets_papers_and_past_dailies(client):
    assert client.get("/api/sudoku/weekly").json() is None
    monday = sudoku.monday(__import__("datetime").date.fromisoformat(client.get("/api/sudoku/summary").json()["today"])).isoformat()
    w = client.post("/api/sudoku/games", json={"puzzle": GIANT, "solution": GIANT_ANSWER, "size": 16, "difficulty": "Hard",
                                               "source": "weekly", "week_of": monday})
    assert w.status_code == 201, w.text
    again = client.post("/api/sudoku/games", json={"puzzle": GIANT, "solution": GIANT_ANSWER, "size": 16, "difficulty": "Hard",
                                                   "source": "weekly", "week_of": monday}).json()
    assert again["game_id"] == w.json()["game_id"] and client.get("/api/sudoku/weekly").json()["game_id"] == again["game_id"]
    tuesday = (sudoku.monday(__import__("datetime").date.fromisoformat(monday)) + __import__("datetime").timedelta(days=1)).isoformat()
    assert client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": SOLUTION, "difficulty": "Hard", "source": "weekly",
                                                  "week_of": tuesday}).status_code == 422          # a week starts on Monday
    s1 = game(client, source="set", set_key="hardest", set_stop=1, difficulty="Extreme")
    assert game(client, source="set", set_key="hardest", set_stop=1, difficulty="Extreme")["game_id"] == s1["game_id"]
    assert client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": SOLUTION, "difficulty": "Easy", "source": "set"}).status_code == 422
    assert list(client.get("/api/sudoku/sets/hardest").json()) == ["1"]
    p = game(client, source="typed", paper=" The Courier-Mail ")
    assert p["paper"] == "The Courier-Mail"
    assert client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": SOLUTION, "difficulty": "Easy", "paper": "NYT"}).status_code == 422
    game(client, source="daily", daily_on="2026-11-01")
    assert [g["daily_on"] for g in client.get("/api/sudoku/dailies?days=400").json()] == ["2026-11-01"]


def test_rating_and_ranks(client):
    assert client.get("/api/sudoku/rating").json()["now"] == 1000
    fast = game(client, difficulty="Hard")
    r = client.patch(f"/api/sudoku/games/{fast['game_id']}", json={"state": state(SOLUTION), "seconds": 300, "status": "solved"}).json()["rating"]
    assert r["change"] > 0 and r["now"] == 1000 + r["change"] and r["score"] == 1.0 and r["puzzle"] == 1300
    slow = game(client, difficulty="Easy", hints=3, mistakes=2)
    r2 = client.patch(f"/api/sudoku/games/{slow['game_id']}", json={"state": state(SOLUTION), "seconds": 900, "status": "solved"}).json()["rating"]
    assert r2["change"] < 0                                          # an easy one, slow, with hints: a loss of rating
    quit_ = game(client, difficulty="Medium")
    r3 = client.patch(f"/api/sudoku/games/{quit_['game_id']}", json={"status": "gave_up"}).json()["rating"]
    assert r3["score"] == 0 and r3["change"] < 0
    lesson = game(client, source="practice", practice="x_wing")
    client.patch(f"/api/sudoku/games/{lesson['game_id']}", json={"state": state(SOLUTION), "status": "solved"})
    full = client.get("/api/sudoku/rating").json()
    assert len(full["games"]) == 3 and full["now"] == r3["now"] and full["rank"]["name"] in ("Apprentice", "Solver", "Novice")
    assert sudoku.rank_of(1250)["name"] == "Adept" and sudoku.rank_of(1250)["next"] == {"name": "Expert", "at": 1400}
    assert client.get("/api/sudoku/summary").json()["rating"]["now"] == full["now"]
    awards = {a["key"]: a for a in client.get("/api/sudoku/achievements").json()}
    assert awards["rank_adept"]["target"] == 1200 and awards["rank_adept"]["progress"] == max(g["after"] for g in full["games"])


def test_more_achievements(client):
    for _ in range(2):
        g = game(client, difficulty="Hard", source="typed", paper="The Age")
        client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": state(SOLUTION), "status": "solved"})
    h = game(client, source="set", set_key="hardest", set_stop=100, difficulty="Extreme")
    done = client.patch(f"/api/sudoku/games/{h['game_id']}", json={"state": state(SOLUTION), "status": "solved"}).json()
    assert {"hardest_1", "hardest_top"} <= {a["key"] for a in done["new_awards"]}
    a = {x["key"]: x for x in client.get("/api/sudoku/achievements").json()}
    assert a["hard_10"]["progress"] == 2 and a["paper"]["unlocked_at"] and a["paper_10"]["progress"] == 2 and a["papers_3"]["progress"] == 1
    assert client.get("/api/sudoku/summary").json()["sets"]["hardest"] == {"solved": 1, "furthest": 100}


def _x_answer() -> str:
    """A full Diagonal (X) grid: backtracking with both diagonals as units."""
    units = sudoku.X_UNITS
    peers = [{p for u in units if c in u for p in u} - {c} for c in range(81)]
    v = [0] * 81

    def go(c):
        if c == 81:
            return True
        for d in range(1, 10):
            if all(v[p] != d for p in peers[c]):
                v[c] = d
                if go(c + 1):
                    return True
        v[c] = 0
        return False
    go(0)
    return "".join(map(str, v))


def test_diagonal_x(client):
    answer = _x_answer()
    puzzle = "".join("0" if c == (r * 4) % 9 else answer[r * 9 + c] for r in range(9) for c in range(9))   # one blank a row
    assert sudoku.solve_count([int(x) for x in puzzle], x=True) == 1
    g = client.post("/api/sudoku/games", json={"puzzle": puzzle, "solution": answer, "variant": "x", "difficulty": "Easy"})
    assert g.status_code == 201, g.text
    assert g.json()["variant"] == "x"
    bad = client.post("/api/sudoku/games", json={"puzzle": PUZZLE, "solution": SOLUTION, "variant": "x", "difficulty": "Easy"})
    assert bad.status_code == 422 and "valid finished grid" in bad.json()["detail"]          # its diagonals repeat
    assert client.post("/api/sudoku/games", json={"puzzle": GIANT, "solution": GIANT_ANSWER, "size": 16, "variant": "x",
                                                  "difficulty": "Easy"}).status_code == 422
    done = client.patch(f"/api/sudoku/games/{g.json()['game_id']}", json={"state": {"v": answer, "n": [0] * 81, "m": [[5, 0, 3], [9, 4, int(answer[4])]]},
                                                                         "status": "solved"}).json()
    assert "x_1" in {a["key"] for a in done["new_awards"]}


def test_moves_make_the_mistake_map_and_advent_counts(client):
    g = game(client)
    wrong_digit = 1 if SOLUTION[2] != "1" else 2
    moves = [[3, 2, wrong_digit], [5, 2, 0], [8, 2, int(SOLUTION[2])]]
    client.patch(f"/api/sudoku/games/{g['game_id']}", json={"state": {"v": SOLUTION, "n": [0] * 81, "m": moves}, "status": "solved"})
    st = client.get("/api/sudoku/stats").json()
    assert st["mistakes_by_cell"][2] == 1 and sum(st["mistakes_by_cell"]) == 1 and st["mistakes_by_digit"] == {str(wrong_digit): 1}
    assert client.get(f"/api/sudoku/games/{g['game_id']}").json()["state"]["m"] == moves
    assert sudoku.event_length("advent-2026") == 24 and sudoku.event_length("grand-tour") == 30 and sudoku.event_length("hardest") is None


def test_library(client):
    empty = client.get("/api/sudoku/library/hardest").json()
    assert empty == {"list": "hardest", "credit": None, "puzzles": []}           # not loaded: the app's own lists
    from app.db import db
    with db() as conn:
        for rank in (1, 2, 101):
            conn.execute("INSERT INTO sudoku_library (list_key, rank, puzzle, measure) VALUES ('hardest', %s, %s, %s)", (rank, PUZZLE, 500 - rank))
    r = client.get("/api/sudoku/library/hardest?first=1&last=100").json()
    assert [p["rank"] for p in r["puzzles"]] == [1, 2] and "tdoku" in r["credit"]
    assert [p["rank"] for p in client.get("/api/sudoku/library/hardest?first=101&last=1000").json()["puzzles"]] == [101]
    assert client.get("/api/sudoku/library/Bad Key").status_code == 422
