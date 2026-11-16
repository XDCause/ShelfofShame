"""Volleyball numbers you enter as you go (market review, 2026-11-16).

    ratings    a tap for each serve or pass in a game or training, 0-3 (0 error, 1 poor, 2 ok, 3 perfect): averages and a trend
    points     OPTIONAL rally by rally: which rotation (1-6) you were in, whether you served, whether you won it. Gives
               side-out % (rallies won when the other team served) and points won when serving, for each rotation.
               (Chosen because it is three taps and no setup; typing a summary per set would say less.)
    drills     a Coach drill can keep results: your best (highest, or lowest for a time) and how much you did each week

The tables are in db/init/A06_reading_vinyl_volleyball.sql. Clips tagged by skill and outcome are in vbclips.py.
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .volleyball import fetch_game

router = APIRouter(prefix="/api", tags=["volleyball"])

RATED = ("serve", "pass")
TREND_GAMES = 5                    # the trend: your last five games' average against the five before


class RatingIn(BaseModel):
    skill: Literal["serve", "pass"]
    score: int = Field(ge=0, le=3)


class PointIn(BaseModel):
    rotation: int = Field(ge=1, le=6)
    serving: bool
    won: bool


class DrillLogIn(BaseModel):
    done_on: date | None = None
    result: float | None = Field(None, ge=0, le=1_000_000)
    reps: int | None = Field(None, gt=0, le=100000)
    minutes: int | None = Field(None, gt=0, le=1440)
    game_id: int | None = None
    note: str | None = Field(None, max_length=500)


class DrillResultIn(BaseModel):
    result_label: str | None = Field(None, max_length=40)
    lower_is_better: bool = False


# ---- pure helpers (tested without a database) ----------------------------------------------

def average(scores: list[int]) -> float | None:
    return round(sum(scores) / len(scores), 2) if scores else None


def rating_trend(games: list[dict]) -> float | None:
    """Your last five games' average minus the five before (None until there are two games to compare, and
    then compares what there is: the latest five against the earlier ones)."""
    if len(games) < 2:
        return None
    recent, before = games[-TREND_GAMES:], games[-2 * TREND_GAMES:-TREND_GAMES]
    if not before:
        half = len(games) // 2
        before, recent = games[:half], games[half:]
    avg = lambda gs: sum(g["avg"] * g["n"] for g in gs) / sum(g["n"] for g in gs)   # noqa: E731 (weighted by taps)
    return round(avg(recent) - avg(before), 2)


def rotation_table(points: list[dict]) -> list[dict]:
    """For rotations 1-6: rallies served / received, points won on serve, side-outs won (received and won)."""
    rows = [{"rotation": r, "serving": 0, "points_won": 0, "receiving": 0, "side_outs": 0} for r in range(1, 7)]
    for p in points:
        row = rows[p["rotation"] - 1]
        if p["serving"]:
            row["serving"] += 1
            row["points_won"] += p["won"]
        else:
            row["receiving"] += 1
            row["side_outs"] += p["won"]
    for row in rows:
        row["side_out_percent"] = round(100 * row["side_outs"] / row["receiving"]) if row["receiving"] else None
        row["point_percent"] = round(100 * row["points_won"] / row["serving"]) if row["serving"] else None
    return rows


def week_of(day: date) -> date:
    return day - timedelta(days=day.weekday())      # the Monday


def best_result(results: list[float], lower_is_better: bool) -> float | None:
    return (min if lower_is_better else max)(results) if results else None


def weekly_volume(logs: list[dict], today: date, weeks: int = 8) -> list[dict]:
    """Reps, minutes and sessions for each of the last `weeks` weeks (Monday to Sunday), oldest first, empty weeks included."""
    start = week_of(today) - timedelta(weeks=weeks - 1)
    out = [{"week": start + timedelta(weeks=i), "reps": 0, "minutes": 0, "sessions": 0} for i in range(weeks)]
    for log in logs:
        i = (week_of(log["done_on"]) - start).days // 7
        if 0 <= i < weeks:
            out[i]["reps"] += log["reps"] or 0
            out[i]["minutes"] += log["minutes"] or 0
            out[i]["sessions"] += 1
    return out


# ---- ratings --------------------------------------------------------------------------------

def game_ratings(conn, game_id: int) -> dict:
    rows = conn.execute("SELECT rating_id, skill, score FROM volleyball_ratings WHERE game_id = %s ORDER BY rating_id", (game_id,)).fetchall()
    out = {"entries": rows}
    for skill in RATED:
        scores = [r["score"] for r in rows if r["skill"] == skill]
        out[skill] = {"n": len(scores), "avg": average(scores), "counts": [scores.count(s) for s in range(4)]}
    return out


@router.get("/volleyball/games/{game_id}/ratings")
def get_game_ratings(game_id: int):
    with db() as conn:
        fetch_game(conn, game_id)
        return game_ratings(conn, game_id)


@router.post("/volleyball/games/{game_id}/ratings", status_code=201)
def add_rating(game_id: int, body: RatingIn):
    """One serve or pass, scored (0 error, 1 poor, 2 ok, 3 perfect)."""
    with db() as conn:
        fetch_game(conn, game_id)
        insert_row(conn, "volleyball_ratings", {"game_id": game_id, **body.model_dump()}, "rating_id")
        return game_ratings(conn, game_id)


@router.delete("/volleyball/ratings/{rating_id}")
def delete_rating(rating_id: int):
    """Take back a tap; answers with that game's ratings."""
    with db() as conn:
        row = found(conn.execute("DELETE FROM volleyball_ratings WHERE rating_id = %s RETURNING game_id", (rating_id,)).fetchone(), "Rating")
        return game_ratings(conn, row["game_id"])


@router.get("/volleyball/ratings")
def ratings_summary():
    """Serve and pass: the overall average, each tap's share, and the average per game (oldest first) with the trend."""
    with db() as conn:
        rows = conn.execute("""
            SELECT r.skill, r.game_id, g.played_on, count(*)::int AS n, avg(r.score)::float8 AS avg
            FROM volleyball_ratings r JOIN volleyball_games g USING (game_id)
            GROUP BY r.skill, r.game_id, g.played_on ORDER BY g.played_on, r.game_id""").fetchall()
        counts = conn.execute("SELECT skill, score, count(*)::int AS n FROM volleyball_ratings GROUP BY 1, 2").fetchall()
    out = {}
    for skill in RATED:
        games = [{"game_id": r["game_id"], "played_on": r["played_on"], "n": r["n"], "avg": round(r["avg"], 2)} for r in rows if r["skill"] == skill]
        dist = [next((c["n"] for c in counts if c["skill"] == skill and c["score"] == s), 0) for s in range(4)]
        total = sum(dist)
        out[skill] = {"n": total, "avg": round(sum(s * n for s, n in enumerate(dist)) / total, 2) if total else None,
                      "counts": dist, "games": games, "trend": rating_trend(games)}
    return out


# ---- points and rotations ---------------------------------------------------------------------

@router.get("/volleyball/games/{game_id}/points")
def game_points(game_id: int):
    """The rallies logged in a game, in order, with the rotation table for it."""
    with db() as conn:
        fetch_game(conn, game_id)
        points = conn.execute("SELECT point_id, rotation, serving, won FROM volleyball_points WHERE game_id = %s ORDER BY point_id",
                              (game_id,)).fetchall()
    return {"points": points, "rotations": rotation_table(points)}


@router.post("/volleyball/games/{game_id}/points", status_code=201)
def add_point(game_id: int, body: PointIn):
    with db() as conn:
        fetch_game(conn, game_id)
        insert_row(conn, "volleyball_points", {"game_id": game_id, **body.model_dump()}, "point_id")
    return game_points(game_id)


@router.delete("/volleyball/points/{point_id}")
def delete_point(point_id: int):
    with db() as conn:
        row = found(conn.execute("DELETE FROM volleyball_points WHERE point_id = %s RETURNING game_id", (point_id,)).fetchone(), "Point")
    return game_points(row["game_id"])


@router.get("/volleyball/rotations")
def rotations(year: int | None = Query(None, ge=1900, le=2100)):
    """Side-out % and points won when serving for each rotation, over every game with rallies logged (or one year)."""
    with db() as conn:
        points = conn.execute("""
            SELECT p.rotation, p.serving, p.won FROM volleyball_points p JOIN volleyball_games g USING (game_id)
            WHERE %(y)s::int IS NULL OR extract(year FROM g.played_on) = %(y)s""", {"y": year}).fetchall()
        games = conn.execute("SELECT count(DISTINCT game_id)::int AS n FROM volleyball_points").fetchone()["n"]
    recv = [p for p in points if not p["serving"]]
    serve = [p for p in points if p["serving"]]
    return {"rotations": rotation_table(points), "games": games, "rallies": len(points),
            "side_out_percent": round(100 * sum(p["won"] for p in recv) / len(recv)) if recv else None,
            "point_percent": round(100 * sum(p["won"] for p in serve) / len(serve)) if serve else None}


# ---- drills -----------------------------------------------------------------------------------

DRILL_SELECT = "SELECT note_id, title, skill, result_label, lower_is_better, pinned FROM volleyball_coach WHERE kind = 'drill'"


def drill_numbers(drill: dict, logs: list[dict], today: date) -> dict:
    results = [float(x["result"]) for x in logs if x["result"] is not None]
    best = best_result(results, drill["lower_is_better"])
    return {**drill, "sessions": len(logs), "reps": sum(x["reps"] or 0 for x in logs), "minutes": sum(x["minutes"] or 0 for x in logs),
            "best": best, "best_on": next((x["done_on"] for x in logs if x["result"] is not None and float(x["result"]) == best), None),
            "last": logs[0] if logs else None, "weeks": weekly_volume(logs, today)}


@router.get("/volleyball/drills")
def drills():
    """Every drill in Coach with your best, how much you've done and the last eight weeks' volume; and the weeks added up."""
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
        notes = conn.execute(DRILL_SELECT + " ORDER BY pinned DESC, lower(title)").fetchall()
        logs = conn.execute("SELECT l.*, l.result::float8 AS result FROM volleyball_drill_logs l ORDER BY done_on DESC, log_id DESC").fetchall()
    out = [drill_numbers(n, [x for x in logs if x["note_id"] == n["note_id"]], today) for n in notes]
    return {"drills": out, "weeks": weekly_volume(logs, today)}


@router.get("/volleyball/coach/{note_id}/logs")
def drill_logs(note_id: int):
    with db() as conn:
        drill = found(conn.execute(DRILL_SELECT + " AND note_id = %s", (note_id,)).fetchone(), "Drill")
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
        logs = conn.execute("SELECT *, result::float8 AS result FROM volleyball_drill_logs WHERE note_id = %s "
                            "ORDER BY done_on DESC, log_id DESC", (note_id,)).fetchall()
    return {**drill_numbers(drill, logs, today), "logs": logs}


@router.post("/volleyball/coach/{note_id}/logs", status_code=201)
def add_drill_log(note_id: int, body: DrillLogIn):
    """You did the drill: a day, and any of a result, reps and minutes."""
    data = tidy_text(body.model_dump())
    if data["result"] is None and data["reps"] is None and data["minutes"] is None:
        raise HTTPException(422, "Add a result, how many you did or how long it took.")
    with db() as conn:
        found(conn.execute(DRILL_SELECT + " AND note_id = %s", (note_id,)).fetchone(), "Drill")
        if data["game_id"] is not None:
            fetch_game(conn, data["game_id"])
        data["done_on"] = data["done_on"] or conn.execute("SELECT current_date AS d").fetchone()["d"]
        insert_row(conn, "volleyball_drill_logs", {"note_id": note_id, **data}, "log_id")
    return drill_logs(note_id)


@router.put("/volleyball/coach/{note_id}/result")
def set_drill_result(note_id: int, body: DrillResultIn):
    """What a drill's result means ("in a row", "out of 20") and whether lower is better (a time)."""
    data = tidy_text(body.model_dump())
    with db() as conn:
        found(conn.execute(DRILL_SELECT + " AND note_id = %s", (note_id,)).fetchone(), "Drill")
        update_row(conn, "volleyball_coach", "note_id", note_id, data)
    return drill_logs(note_id)


@router.delete("/volleyball/drill-logs/{log_id}", status_code=204)
def delete_drill_log(log_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM volleyball_drill_logs WHERE log_id = %s RETURNING log_id", (log_id,)).fetchone(), "Drill log")
    return Response(status_code=204)
