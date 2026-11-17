"""Golf rounds (A08_golf.sql; scored in golf_scores.py): played live on the phone hole by hole, or typed in after.

    GET  /golf/rounds?course_id=&year=          rounds, newest first, with their totals
    POST /golf/rounds                           start one (your handicap and daily handicap are kept as they were)
    GET / PATCH / DELETE /golf/rounds/{id}      the scorecard: every hole (par, index, metres, map), score, points...
    PUT  /golf/rounds/{id}/holes/{no}           one hole's score (sent again safely: the phone resends when it was offline)
    PUT  /golf/rounds/{id}/holes                many holes at once (the scorecard typed in after)
    PUT  /golf/rounds/{id}/shots/{no}/{seq}     a shot marked on the course (GPS, club, lie); DELETE the same to remove
    GET  /golf/summary                          Home and the dashboard: the handicap, this year, the last rounds, stats
    GET  /golf/stats?last=&course_id=           stats over your last N rounds: rates, plays-like, strokes gained, trends
    GET  /golf/handicap                         the estimate's last 20 (which count), its history, what to shoot
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from . import golf_scores, golfmath as gm, openmeteo
from .db import db, found, insert_row, tidy_text, update_row
from .golf import FAIRWAYS, FORMATS, LIES, _lit, _required

router = APIRouter(prefix="/api", tags=["golf"])


def _round(conn, round_id: int, with_map: bool = True) -> dict:
    got = golf_scores.load(conn, "r.round_id = %s", (round_id,), with_map=with_map)
    r = found(got[0] if got else None, "Round")
    r["shots"] = conn.execute("""SELECT s.shot_id, s.hole_no, s.seq, s.club_id, c.name AS club, s.lie, s.lat, s.lon, s.accuracy_m
                                 FROM golf_shots s LEFT JOIN golf_clubs c USING (club_id)
                                 WHERE s.round_id = %s ORDER BY s.hole_no, s.seq""", (round_id,)).fetchall()
    # each shot's distance: to the next one marked on the hole
    for a, b in zip(r["shots"], r["shots"][1:]):
        if a["hole_no"] == b["hole_no"] and b["seq"] == a["seq"] + 1:
            a["metres"] = round(gm.metres_between((a["lat"], a["lon"]), (b["lat"], b["lon"])))
    return r


def _brief(r: dict) -> dict:
    t = r["totals"]
    return {"round_id": r["round_id"], "played_on": r["played_on"], "course_id": r["course_id"], "course_name": r["course_name"],
            "tee_name": r["tee_name"], "tee_colour": r["tee_colour"], "holes": r["hole_set"], "format": r["format"],
            "status": r["status"], "competition": r["competition"], "counts": r["counts"],
            "daily_handicap": r["daily_handicap"], "gross": t["gross"], "to_par": t["to_par"], "par": t["par"],
            "points": t["points"], "net": t["net"], "entered": t["entered"], "of": t["holes"],
            "differential": t["differential"], "putts": r["stats"]["putts"] if r["stats"]["putt_holes"] == t["holes"] else None,
            "gir": r["stats"]["gir"], "fairways": r["stats"]["fairways"], "fairway_chances": r["stats"]["fairway_chances"]}


@router.get("/golf/rounds")
def list_rounds(course_id: int | None = Query(None, ge=1), year: int | None = Query(None, ge=1900, le=2200)):
    where, params = ["TRUE"], []
    if course_id:
        where.append("r.course_id = %s")
        params.append(course_id)
    if year:
        where.append("extract(year FROM r.played_on) = %s")
        params.append(year)
    with db() as conn:
        rounds = golf_scores.load(conn, " AND ".join(where), params)
        hcp = golf_scores.handicap(conn) if rounds else {"used": []}
    used = set(hcp["used"])
    return [{**_brief(r), "counted": r["round_id"] in used} for r in rounds]


class RoundFields(BaseModel):
    tee_id: int | None = None
    played_on: date | None = None
    holes: str | None = Field(None, pattern="^(18|front|back)$")
    format: str | None = Field(None, pattern=_lit(FORMATS))
    counts: bool | None = None
    competition: str | None = Field(None, max_length=120)
    partners: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=5000)
    status: str | None = Field(None, pattern="^(playing|done)$")
    handicap: float | None = Field(None, ge=-10, le=54)


class RoundIn(RoundFields):
    course_id: int


class RoundPatch(RoundFields):
    pass


def _daily(conn, course_id: int, tee_id, holes: str, index) -> int | None:
    """Today's handicap from the tee's rating and slope (none without them, or without an index)."""
    if tee_id is None or index is None:
        return None
    t = conn.execute("SELECT rating, slope FROM golf_tees WHERE tee_id = %s", (tee_id,)).fetchone()
    c = conn.execute("SELECT holes FROM golf_courses WHERE course_id = %s", (course_id,)).fetchone()
    if not t or t["rating"] is None or not t["slope"]:
        return None
    nos = golf_scores.played({"holes": holes}, c["holes"])
    par = conn.execute("SELECT COALESCE(sum(par), 0)::int AS p FROM golf_holes WHERE course_id = %s AND hole_no = ANY(%s)",
                       (course_id, nos)).fetchone()["p"]
    nine = len(nos) == 9
    rating = float(t["rating"]) / 2 if nine and c["holes"] == 18 else float(t["rating"])
    allowance = golf_scores.settings(conn)["allowance"]
    return gm.daily_handicap(index, t["slope"], rating, par, allowance, nine=nine)


def _weather(conn, round_id: int):
    """The day's weather where the course is, kept on the round when it's finished (Open-Meteo keeps 92 days back)."""
    r = conn.execute("""SELECT r.played_on, c.lat, c.lon FROM golf_rounds r JOIN golf_courses c USING (course_id)
                        WHERE r.round_id = %s AND r.weather IS NULL""", (round_id,)).fetchone()
    if not r or r["lat"] is None or (date.today() - r["played_on"]).days > 90 or r["played_on"] > date.today():
        return
    try:
        w = openmeteo.day_weather(r["lat"], r["lon"], r["played_on"].isoformat())
    except Exception:               # (no weather is fine: it's a nicety)
        return
    if w:
        conn.execute("UPDATE golf_rounds SET weather = %s WHERE round_id = %s", (Jsonb(w), round_id))


@router.post("/golf/rounds", status_code=201)
def add_round(body: RoundIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
    with db() as conn:
        found(conn.execute("SELECT 1 FROM golf_courses WHERE course_id = %s", (body.course_id,)).fetchone(), "Course")
        if body.tee_id is not None and not conn.execute("SELECT 1 FROM golf_tees WHERE tee_id = %s AND course_id = %s",
                                                        (body.tee_id, body.course_id)).fetchone():
            raise HTTPException(422, "Those tees aren't this course's.")
        if "handicap" not in data:
            data["handicap"] = golf_scores.handicap(conn)["current"]
        if body.format in golf_scores.TEAM and body.counts is None:
            data["counts"] = False
        data["daily_handicap"] = _daily(conn, body.course_id, body.tee_id, data.get("holes", "18"), data["handicap"])
        if data.get("status") == "done":
            data["finished_at"] = conn.execute("SELECT now() AS t").fetchone()["t"]
        round_id = insert_row(conn, "golf_rounds", data, "round_id")
        if data.get("status") == "done":
            _weather(conn, round_id)
        return _round(conn, round_id)


@router.get("/golf/rounds/{round_id}")
def get_round(round_id: int):
    with db() as conn:
        return _round(conn, round_id)


@router.patch("/golf/rounds/{round_id}")
def update_round(round_id: int, body: RoundPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    _required(data, "played_on", "holes", "format", "counts", "status")
    with db() as conn:
        r = found(conn.execute("SELECT * FROM golf_rounds WHERE round_id = %s", (round_id,)).fetchone(), "Round")
        if "tee_id" in data and data["tee_id"] is not None and not conn.execute(
                "SELECT 1 FROM golf_tees WHERE tee_id = %s AND course_id = %s", (data["tee_id"], r["course_id"])).fetchone():
            raise HTTPException(422, "Those tees aren't this course's.")
        if {"tee_id", "holes", "handicap"} & set(data):
            merged = {**r, **data}
            data["daily_handicap"] = _daily(conn, r["course_id"], merged["tee_id"], merged["holes"], merged["handicap"])
        if data.get("status") == "done" and r["status"] != "done":
            data["finished_at"] = conn.execute("SELECT now() AS t").fetchone()["t"]
        elif data.get("status") == "playing":
            data["finished_at"] = None
        update_row(conn, "golf_rounds", "round_id", round_id, data)
        if data.get("status") == "done" or "played_on" in data:
            if "played_on" in data:
                conn.execute("UPDATE golf_rounds SET weather = NULL WHERE round_id = %s", (round_id,))
            _weather(conn, round_id)
        return _round(conn, round_id)


@router.delete("/golf/rounds/{round_id}", status_code=204)
def delete_round(round_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM golf_rounds WHERE round_id = %s RETURNING round_id", (round_id,)).fetchone(), "Round")
    return Response(status_code=204)


class HoleScore(BaseModel):
    strokes: int | None = Field(None, ge=1, le=20)
    putts: int | None = Field(None, ge=0, le=10)
    fairway: str | None = Field(None, pattern=_lit(FAIRWAYS))
    penalties: int = Field(0, ge=0, le=10)
    sand: int = Field(0, ge=0, le=10)
    first_putt_m: float | None = Field(None, ge=0, le=99)
    picked_up: bool = False


class HoleScoreNo(HoleScore):
    hole_no: int = Field(ge=1, le=18)


def _save_hole(conn, r: dict, no: int, s: HoleScore):
    if no not in golf_scores.played(r, r["course_holes"]):
        raise HTTPException(422, f"Hole {no} isn't part of this round.")
    if s.picked_up and s.strokes is not None:
        raise HTTPException(422, "A picked-up hole has no score.")
    if s.strokes is not None and s.putts is not None and s.putts + s.penalties > s.strokes:
        raise HTTPException(422, "More putts and penalties than strokes.")
    if s.strokes is None and not s.picked_up:
        conn.execute("DELETE FROM golf_round_holes WHERE round_id = %s AND hole_no = %s", (r["round_id"], no))
        return
    conn.execute("""INSERT INTO golf_round_holes (round_id, hole_no, strokes, putts, fairway, penalties, sand, first_putt_m, picked_up)
                    VALUES (%(r)s, %(n)s, %(strokes)s, %(putts)s, %(fairway)s, %(penalties)s, %(sand)s, %(first_putt_m)s, %(picked_up)s)
                    ON CONFLICT (round_id, hole_no) DO UPDATE SET strokes = EXCLUDED.strokes, putts = EXCLUDED.putts,
                        fairway = EXCLUDED.fairway, penalties = EXCLUDED.penalties, sand = EXCLUDED.sand,
                        first_putt_m = EXCLUDED.first_putt_m, picked_up = EXCLUDED.picked_up""",
                 {"r": r["round_id"], "n": no, **s.model_dump()})


def _round_row(conn, round_id: int) -> dict:
    return found(conn.execute("""SELECT r.round_id, r.holes, c.holes AS course_holes FROM golf_rounds r
                                 JOIN golf_courses c USING (course_id) WHERE r.round_id = %s""", (round_id,)).fetchone(), "Round")


@router.put("/golf/rounds/{round_id}/holes/{hole_no}")
def put_hole(round_id: int, hole_no: int, body: HoleScore):
    """One hole's score (no strokes and not picked up: the hole is cleared). Answers with the whole round."""
    with db() as conn:
        _save_hole(conn, _round_row(conn, round_id), hole_no, body)
        return _round(conn, round_id)


@router.put("/golf/rounds/{round_id}/holes")
def put_holes(round_id: int, body: list[HoleScoreNo]):
    with db() as conn:
        r = _round_row(conn, round_id)
        for h in body:
            _save_hole(conn, r, h.hole_no, h)
        return _round(conn, round_id)


class ShotIn(BaseModel):
    lie: str = Field(pattern=_lit(LIES))
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    club_id: int | None = None
    accuracy_m: float | None = Field(None, ge=0, le=10000)


@router.put("/golf/rounds/{round_id}/shots/{hole_no}/{seq}")
def put_shot(round_id: int, hole_no: int, seq: int, body: ShotIn):
    """A shot marked where the ball lay (seq: the shot's number on the hole). Answers with the whole round."""
    if not 1 <= seq <= 20:
        raise HTTPException(422, "A shot's number is 1 to 20.")
    with db() as conn:
        r = _round_row(conn, round_id)
        if hole_no not in golf_scores.played(r, r["course_holes"]):
            raise HTTPException(422, f"Hole {hole_no} isn't part of this round.")
        if body.club_id is not None:
            found(conn.execute("SELECT 1 FROM golf_clubs WHERE club_id = %s", (body.club_id,)).fetchone(), "Club")
        conn.execute("""INSERT INTO golf_shots (round_id, hole_no, seq, club_id, lie, lat, lon, accuracy_m)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (round_id, hole_no, seq) DO UPDATE SET club_id = EXCLUDED.club_id, lie = EXCLUDED.lie,
                            lat = EXCLUDED.lat, lon = EXCLUDED.lon, accuracy_m = EXCLUDED.accuracy_m""",
                     (round_id, hole_no, seq, body.club_id, body.lie, body.lat, body.lon, body.accuracy_m))
        return _round(conn, round_id)


@router.delete("/golf/rounds/{round_id}/shots/{hole_no}/{seq}")
def delete_shot(round_id: int, hole_no: int, seq: int):
    """Remove a marked shot (the later ones on the hole move up a number). Answers with the whole round."""
    with db() as conn:
        _round_row(conn, round_id)
        found(conn.execute("DELETE FROM golf_shots WHERE round_id = %s AND hole_no = %s AND seq = %s RETURNING shot_id",
                           (round_id, hole_no, seq)).fetchone(), "Shot")
        later = conn.execute("SELECT shot_id FROM golf_shots WHERE round_id = %s AND hole_no = %s AND seq > %s ORDER BY seq",
                             (round_id, hole_no, seq)).fetchall()
        for i, s in enumerate(later):
            conn.execute("UPDATE golf_shots SET seq = %s WHERE shot_id = %s", (seq + i, s["shot_id"]))
        return _round(conn, round_id)


# ---------------------------------------------------------------- the numbers

def _trend(rounds: list[dict]) -> list[dict]:
    """Oldest first: each finished round's score (18 holes: gross; 9: its points / to-par), for the charts."""
    out = []
    for r in reversed(rounds):
        t = r["totals"]
        if not t["complete"]:
            continue
        out.append({"day": r["played_on"], "round_id": r["round_id"], "gross": t["gross"] if not t["nine"] else None,
                    "to_par": t["to_par"], "points": t["points"] if r["format"] == "Stableford" else None,
                    "nine": t["nine"], "differential": t["differential"], "course": r["course_name"]})
    return out


@router.get("/golf/summary")
def summary():
    with db() as conn:
        rounds = golf_scores.load(conn, "r.status = 'done'")
        playing = golf_scores.load(conn, "r.status = 'playing'")
        hcp = golf_scores.handicap(conn, rounds)
        year = conn.execute("SELECT extract(year FROM current_date)::int AS y").fetchone()["y"]
        practice = conn.execute("""SELECT count(*)::int AS sessions, COALESCE(sum(minutes), 0)::int AS minutes FROM golf_practice
                                   WHERE practiced_on >= date_trunc('year', current_date)""").fetchone()
        courses = conn.execute("SELECT count(*)::int AS n FROM golf_courses").fetchone()["n"]
        clubs = conn.execute("SELECT count(*)::int AS n FROM golf_clubs WHERE in_bag").fetchone()["n"]
    this_year = [r for r in rounds if r["played_on"].year == year]
    last20 = rounds[:20]
    stats = golf_scores.summarise(last20)
    target = hcp["target"] if hcp["target"] is not None else (max(0, round(hcp["current"] - 5)) if hcp["current"] is not None else None)
    return {
        "year": year, "handicap": {k: v for k, v in hcp.items() if k != "history"},
        "handicap_trend": hcp["history"][-30:],
        "rounds": len(rounds), "this_year": {"rounds": len(this_year), "holes": sum(r["totals"]["holes"] for r in this_year),
                                             "practice": practice},
        "playing": [_brief(r) for r in playing], "recent": [_brief(r) for r in rounds[:8]],
        "best": sorted((_brief(r) for r in rounds if r["totals"]["gross"] is not None and not r["totals"]["nine"]),
                       key=lambda b: (b["gross"], b["played_on"]))[:5],
        "stats": stats, "target": target,
        "bench": {k: gm.bench_at(k, target) for k in gm.BENCH} if target is not None else None,
        "trend": _trend(rounds[:40]), "courses": courses, "clubs": clubs,
    }


@router.get("/golf/stats")
def stats(last: int = Query(20, ge=1, le=1000), course_id: int | None = Query(None, ge=1)):
    """Your last N finished rounds (at one course, if given): every stat, plays-like, strokes gained, and by month."""
    where, params = "r.status = 'done'", []
    if course_id:
        where += " AND r.course_id = %s"
        params.append(course_id)
    with db() as conn:
        rounds = golf_scores.load(conn, where, params)[:last]
        hcp = golf_scores.handicap(conn)
    out = golf_scores.summarise(rounds)
    target = hcp["target"] if hcp["target"] is not None else (max(0, round(hcp["current"] - 5)) if hcp["current"] is not None else None)
    out["target"] = target
    out["bench"] = {k: gm.bench_at(k, target) for k in gm.BENCH} if target is not None else None
    out["trend"] = _trend(rounds)
    # front nine vs back nine, and how each kind of hole goes
    for half, nos in (("front", range(1, 10)), ("back", range(10, 19))):
        diffs = [h["strokes"] - h["par"] for r in rounds for h in r["holes"] if h["hole_no"] in nos and h["strokes"] is not None]
        out[f"{half}_vs_par"] = round(9 * sum(diffs) / len(diffs), 1) if diffs else None
    pts = [r["totals"]["points"] for r in rounds if r["format"] == "Stableford" and r["totals"]["complete"] and not r["totals"]["nine"]]
    out["points_trend"] = pts[::-1]
    return out


@router.get("/golf/handicap")
def handicap():
    """The last 20 counting rounds (newest first) with their differentials and which count, the history, and the
    differential you'd need next time to bring the estimate down."""
    with db() as conn:
        rounds = golf_scores.load(conn, "r.status = 'done'")
        hcp = golf_scores.handicap(conn, rounds)
        s = golf_scores.settings(conn)
        home = conn.execute("""SELECT c.course_id, c.name, t.tee_id, t.name AS tee_name, t.rating, t.slope,
                                      (SELECT sum(par) FROM golf_holes h WHERE h.course_id = c.course_id)::int AS par
                               FROM golf_courses c JOIN golf_tees t USING (course_id)
                               WHERE c.course_id = %s AND t.rating IS NOT NULL AND t.slope IS NOT NULL
                               ORDER BY t.position, t.tee_id LIMIT 1""", (s["home_course_id"],)).fetchone() if s["home_course_id"] else None
    counting = [r for r in rounds if r["totals"]["differential"] is not None][:20]
    used = set(hcp["used"])
    rows = [{**_brief(r), "counted": r["round_id"] in used} for r in counting]
    need = None
    if len(counting) >= 19 and hcp["estimate"] is not None:
        # next round pushes out the oldest: the 8th best of the 19 newest + yours must beat today's
        keep = sorted(r["totals"]["differential"] for r in counting[:19])
        cut = keep[7] if len(keep) >= 8 else None
        if cut is not None:
            need = {"differential": round(cut - 0.1, 1)}
            if home:
                need["course"] = home["name"]
                need["tees"] = home["tee_name"]
                need["gross"] = int(cut * home["slope"] / 113 + float(home["rating"]))   # adjusted gross at or under
    return {**hcp, "rounds": rows, "need": need}
