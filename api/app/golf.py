"""Golf (A08_golf.sql): courses (by hand, or from OpenStreetMap with every hole's map), their tees (rating and slope),
your bag, practice, and the settings. Rounds, the handicap and the stats are in golf_rounds.py; scoring in
golf_scores.py; the sums in golfmath.py; reading OpenStreetMap's shapes in golf_map.py.

    GET  /golf/lists                          the choices (formats, clubs, practice kinds...)
    GET / PUT /golf/settings                  official GA Handicap, the daily handicap allowance, your target
    GET  /golf/osm/search?q= | lat=&lon=      courses near a place (Open-Meteo's place search) or a point (OpenStreetMap)
    POST /golf/osm/import                     {osm}: a course with its holes and maps (again: the maps refreshed)
    GET / POST /golf/courses                  with your rounds there, best and average
    GET / PATCH / DELETE /golf/courses/{id}   + tees, holes (maps too) and how you play each hole
    PUT  /golf/courses/{id}/holes             every hole's par and stroke index
    POST /golf/courses/{id}/tees, PATCH / DELETE /golf/tees/{id}   (lengths: each hole's metres)
    GET / POST /golf/clubs, PATCH / DELETE /golf/clubs/{id}; POST /golf/clubs/standard-bag
    GET / POST /golf/practice, PATCH / DELETE /golf/practice/{id}

Course ratings and slopes are typed (Golf Australia publishes them per course); nothing is read from club websites.
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from . import golf_map, golf_scores, golfmath as gm, openmeteo, overpass
from .db import db, found, insert_row, tidy_text, update_row

router = APIRouter(prefix="/api", tags=["golf"])

FORMATS = ["Stableford", "Stroke", "Par", "Ambrose", "Social"]
HOLE_SETS = [["18", "18 holes"], ["front", "Front 9"], ["back", "Back 9"]]
FAIRWAYS = ["left", "hit", "right", "short", "long"]
LIES = ["tee", "fairway", "rough", "sand", "recovery"]
CLUB_KINDS = ["Driver", "Wood", "Hybrid", "Iron", "Wedge", "Putter"]
PRACTICE_KINDS = ["Range", "Putting", "Chipping", "Bunker", "Lesson", "Simulator", "Course"]
GENDERS = ["Men", "Women"]
# A typical 14 (the rules' most): name, kind, loft, a mid-handicap carry in metres - edit them to yours.
STANDARD_BAG = [("Driver", "Driver", 10.5, 200), ("3 wood", "Wood", 15, 180), ("4 hybrid", "Hybrid", 22, 165),
                ("5 iron", "Iron", 24, 155), ("6 iron", "Iron", 27, 145), ("7 iron", "Iron", 31, 135),
                ("8 iron", "Iron", 35, 125), ("9 iron", "Iron", 40, 115), ("Pitching wedge", "Wedge", 45, 105),
                ("Gap wedge", "Wedge", 50, 90), ("Sand wedge", "Wedge", 56, 75), ("Lob wedge", "Wedge", 60, 55),
                ("Putter", "Putter", 3, None)]


def _lit(values) -> str:
    return "^(" + "|".join(values) + ")$"


def _required(data: dict, *names):
    for n in names:
        if n in data and data[n] is None:
            raise HTTPException(422, f"{n.replace('_', ' ').capitalize()} can't be empty.")


@router.get("/golf/lists")
def lists():
    return {"formats": FORMATS, "hole_sets": HOLE_SETS, "fairways": FAIRWAYS, "lies": LIES, "club_kinds": CLUB_KINDS,
            "practice_kinds": PRACTICE_KINDS, "genders": GENDERS}


# ---------------------------------------------------------------- settings

class SettingsIn(BaseModel):
    official_handicap: float | None = Field(None, ge=-10, le=54)
    official_as_of: date | None = None
    allowance: float | None = Field(None, ge=0.5, le=1)
    target_handicap: float | None = Field(None, ge=-10, le=54)
    home_course_id: int | None = None


@router.get("/golf/settings")
def get_settings():
    with db() as conn:
        return golf_scores.settings(conn)


@router.put("/golf/settings")
def put_settings(body: SettingsIn):
    data = body.model_dump(exclude_unset=True)
    _required(data, "allowance")
    with db() as conn:
        if data.get("home_course_id") is not None:
            found(conn.execute("SELECT 1 FROM golf_courses WHERE course_id = %s", (data["home_course_id"],)).fetchone(), "Course")
        if data:
            update_row(conn, "golf_settings", "id", 1, data)
            conn.execute("UPDATE golf_settings SET updated_at = now() WHERE id = 1")
        return golf_scores.settings(conn)


# ---------------------------------------------------------------- OpenStreetMap

@router.get("/golf/osm/search")
def osm_search(q: str | None = Query(None, min_length=2, max_length=80), lat: float | None = Query(None, ge=-90, le=90),
               lon: float | None = Query(None, ge=-180, le=180)):
    """Golf courses mapped on OpenStreetMap within 25 km of a place (by name) or a point (your phone's location)."""
    if q and (lat is None or lon is None):
        try:
            places = openmeteo.find_place(q.strip())
        except openmeteo.WeatherError as e:
            raise HTTPException(502, str(e))
        if not places:
            return {"place": None, "courses": []}
        lat, lon, where = places[0]["lat"], places[0]["lon"], ", ".join(filter(None, [places[0]["name"], places[0]["region"]]))
    elif lat is not None and lon is not None:
        where = None
    else:
        raise HTTPException(422, "Give a place, or a latitude and longitude.")
    try:
        courses = golf_map.courses(overpass.golf_courses_near(lat, lon))
    except overpass.OverpassError as e:
        raise HTTPException(502, str(e))
    with db() as conn:
        have = {r["osm"]: r["course_id"] for r in conn.execute("SELECT osm, course_id FROM golf_courses WHERE osm IS NOT NULL")}
    for c in courses:
        c["metres"] = round(gm.metres_between((lat, lon), (c["lat"], c["lon"])))
        c["course_id"] = have.get(c["osm"])
    courses.sort(key=lambda c: c["metres"])
    return {"place": where, "courses": courses}


class ImportIn(BaseModel):
    osm: str = Field(pattern=r"^(way|relation)/[0-9]{1,12}$")


@router.post("/golf/osm/import", status_code=201)
def osm_import(body: ImportIn):
    """A course from OpenStreetMap: its name, middle and every mapped hole (par, stroke index, map). Imported again,
    only the maps (and pars / indexes OpenStreetMap has) are refreshed: your tees, ratings and edits stay."""
    try:
        got = golf_map.holes(overpass.golf_course(body.osm))
    except overpass.OverpassError as e:
        raise HTTPException(502, str(e))
    if not got["name"] and not got["holes"]:
        raise HTTPException(404, "OpenStreetMap has no golf course there.")
    with db() as conn:
        row = conn.execute("SELECT course_id FROM golf_courses WHERE osm = %s", (body.osm,)).fetchone()
        nholes = 9 if got["holes"] and max(h["hole_no"] for h in got["holes"]) <= 9 else 18
        if row:
            course_id = row["course_id"]
        else:
            course_id = insert_row(conn, "golf_courses", {
                "name": got["name"] or "Golf course", "place": got["place"], "lat": got["lat"], "lon": got["lon"],
                "holes": nholes, "osm": body.osm, "website": got["website"]}, "course_id")
            _make_holes(conn, course_id, nholes)
        size = conn.execute("SELECT holes FROM golf_courses WHERE course_id = %s", (course_id,)).fetchone()["holes"]
        for h in got["holes"]:
            if h["hole_no"] > size:
                continue
            conn.execute("""INSERT INTO golf_holes (course_id, hole_no, par, stroke_index, map)
                            VALUES (%s, %s, COALESCE(%s, 4), %s, %s)
                            ON CONFLICT (course_id, hole_no) DO UPDATE SET map = EXCLUDED.map,
                                par = COALESCE(%s, golf_holes.par),
                                stroke_index = COALESCE(EXCLUDED.stroke_index, golf_holes.stroke_index)""",
                         (course_id, h["hole_no"], h["par"], h["stroke_index"], Jsonb(h["map"]), h["par"]))
        return course_detail(conn, course_id)


# ---------------------------------------------------------------- courses

class CourseFields(BaseModel):
    place: str | None = Field(None, max_length=120)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    website: str | None = Field(None, max_length=300)
    notes: str | None = Field(None, max_length=5000)


class CourseIn(CourseFields):
    name: str = Field(min_length=1, max_length=120)
    holes: int = Field(18, ge=9, le=18)
    pars: list[int] | None = Field(None, min_length=9, max_length=18)


class CoursePatch(CourseFields):
    name: str | None = Field(None, min_length=1, max_length=120)
    holes: int | None = Field(None, ge=9, le=18)


COURSE_SELECT = """SELECT c.course_id, c.name, c.place, c.lat, c.lon, c.holes, c.osm, c.website, c.notes,
       (SELECT sum(par) FROM golf_holes h WHERE h.course_id = c.course_id)::int AS par,
       (SELECT count(*) FROM golf_holes h WHERE h.course_id = c.course_id AND h.map IS NOT NULL)::int AS mapped,
       (SELECT count(*) FROM golf_rounds r WHERE r.course_id = c.course_id AND r.status = 'done')::int AS rounds,
       (SELECT max(played_on) FROM golf_rounds r WHERE r.course_id = c.course_id) AS last_played,
       (SELECT count(*) FROM golf_tees t WHERE t.course_id = c.course_id)::int AS tees,
       (SELECT count(*) FROM golf_tees t WHERE t.course_id = c.course_id AND t.rating IS NOT NULL AND t.slope IS NOT NULL)::int AS rated
FROM golf_courses c"""


def _make_holes(conn, course_id: int, n: int, pars=None):
    for no in range(1, n + 1):
        conn.execute("INSERT INTO golf_holes (course_id, hole_no, par) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                     (course_id, no, (pars[no - 1] if pars and no <= len(pars) else 4)))


def tees_of(conn, course_id: int) -> list[dict]:
    tees = conn.execute("SELECT * FROM golf_tees WHERE course_id = %s ORDER BY position, tee_id", (course_id,)).fetchall()
    lengths = conn.execute("""SELECT l.tee_id, l.hole_no, l.metres FROM golf_hole_lengths l JOIN golf_tees t USING (tee_id)
                              WHERE t.course_id = %s ORDER BY l.hole_no""", (course_id,)).fetchall()
    for t in tees:
        t["lengths"] = {l["hole_no"]: l["metres"] for l in lengths if l["tee_id"] == t["tee_id"]}
        t["metres"] = sum(t["lengths"].values()) or None
    return tees


def course_detail(conn, course_id: int) -> dict:
    c = found(conn.execute(COURSE_SELECT + " WHERE c.course_id = %s", (course_id,)).fetchone(), "Course")
    c["tees"] = tees_of(conn, course_id)
    c["holes_list"] = conn.execute("SELECT hole_no, par, stroke_index, map FROM golf_holes WHERE course_id = %s "
                                   "ORDER BY hole_no", (course_id,)).fetchall()
    rounds = golf_scores.load(conn, "r.course_id = %s AND r.status = 'done'", (course_id,))
    hcp = golf_scores.handicap(conn)
    allowance = hcp["allowance"]
    for t in c["tees"]:
        par18 = sum(h["par"] for h in c["holes_list"])
        t["daily_handicap"] = gm.daily_handicap(hcp["current"], t["slope"], t["rating"], par18, allowance) \
            if t["rating"] is not None and t["slope"] else None
    # how you play each hole: average, vs par, best, and how often you score par or better
    per = {}
    for r in rounds:
        for h in r["holes"]:
            if h["entered"]:
                p = per.setdefault(h["hole_no"], {"n": 0, "sum": 0, "best": None, "par_or_better": 0, "points": 0, "pickups": 0})
                p["n"] += 1
                p["points"] += h["points"] or 0
                if h["strokes"] is None:
                    p["pickups"] += 1
                    p["sum"] += h["adjusted"]
                else:
                    p["sum"] += h["strokes"]
                    p["best"] = h["strokes"] if p["best"] is None else min(p["best"], h["strokes"])
                    p["par_or_better"] += h["strokes"] <= h["par"]
    for h in c["holes_list"]:
        p = per.get(h["hole_no"])
        h["you"] = p and {"played": p["n"], "average": round(p["sum"] / p["n"], 2), "vs_par": round(p["sum"] / p["n"] - h["par"], 2),
                          "best": p["best"], "par_or_better": round(100 * p["par_or_better"] / p["n"]),
                          "points": round(p["points"] / p["n"], 1)}
    full = [r for r in rounds if r["totals"]["gross"] is not None and not r["totals"]["nine"]]
    c["you"] = {"rounds": len(rounds), "best": min((r["totals"]["gross"] for r in full), default=None),
                "average": round(sum(r["totals"]["gross"] for r in full) / len(full), 1) if full else None,
                "best_points": max((r["totals"]["points"] for r in rounds if not r["totals"]["nine"]), default=None)}
    c["recent"] = [{"round_id": r["round_id"], "played_on": r["played_on"], "tee_name": r["tee_name"], "holes": r["hole_set"],
                    "gross": r["totals"]["gross"], "to_par": r["totals"]["to_par"], "points": r["totals"]["points"]}
                   for r in rounds[:10]]
    return c


@router.get("/golf/courses")
def list_courses():
    with db() as conn:
        courses = conn.execute(COURSE_SELECT + " ORDER BY last_played DESC NULLS LAST, lower(c.name)").fetchall()
        rounds = golf_scores.load(conn, "r.status = 'done'")
    for c in courses:
        mine = [r for r in rounds if r["course_id"] == c["course_id"] and r["totals"]["gross"] is not None and not r["totals"]["nine"]]
        c["best"] = min((r["totals"]["gross"] for r in mine), default=None)
        c["average"] = round(sum(r["totals"]["gross"] for r in mine) / len(mine), 1) if mine else None
    return courses


@router.post("/golf/courses", status_code=201)
def add_course(body: CourseIn):
    if body.holes not in (9, 18):
        raise HTTPException(422, "A course has 9 or 18 holes.")
    if body.pars and (len(body.pars) != body.holes or any(p < 3 or p > 6 for p in body.pars)):
        raise HTTPException(422, f"Give {body.holes} pars, each 3 to 6.")
    data = tidy_text({k: v for k, v in body.model_dump(exclude={"pars"}).items() if v is not None}, required=("name",))
    with db() as conn:
        course_id = insert_row(conn, "golf_courses", data, "course_id")
        _make_holes(conn, course_id, body.holes, body.pars)
        return course_detail(conn, course_id)


@router.get("/golf/courses/{course_id}")
def get_course(course_id: int):
    with db() as conn:
        return course_detail(conn, course_id)


@router.patch("/golf/courses/{course_id}")
def update_course(course_id: int, body: CoursePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "holes")
    if data.get("holes") not in (None, 9, 18):
        raise HTTPException(422, "A course has 9 or 18 holes.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM golf_courses WHERE course_id = %s", (course_id,)).fetchone(), "Course")
        update_row(conn, "golf_courses", "course_id", course_id, data)
        if data.get("holes") == 18:
            _make_holes(conn, course_id, 18)
        elif data.get("holes") == 9:
            conn.execute("DELETE FROM golf_holes WHERE course_id = %s AND hole_no > 9", (course_id,))
        return course_detail(conn, course_id)


@router.delete("/golf/courses/{course_id}", status_code=204)
def delete_course(course_id: int):
    with db() as conn:
        n = conn.execute("SELECT count(*) AS n FROM golf_rounds WHERE course_id = %s", (course_id,)).fetchone()["n"]
        if n:
            raise HTTPException(409, f"You've played {n} round{'s' if n != 1 else ''} there: remove {'them' if n != 1 else 'it'} first.")
        found(conn.execute("DELETE FROM golf_courses WHERE course_id = %s RETURNING course_id", (course_id,)).fetchone(), "Course")
    return Response(status_code=204)


class HoleIn(BaseModel):
    hole_no: int = Field(ge=1, le=18)
    par: int = Field(ge=3, le=6)
    stroke_index: int | None = Field(None, ge=1, le=18)


@router.put("/golf/courses/{course_id}/holes")
def put_holes(course_id: int, body: list[HoleIn]):
    """Every hole's par and stroke index (each index once)."""
    sis = [h.stroke_index for h in body if h.stroke_index is not None]
    if len(sis) != len(set(sis)):
        raise HTTPException(422, "Each stroke index can be used once.")
    with db() as conn:
        c = found(conn.execute("SELECT holes FROM golf_courses WHERE course_id = %s", (course_id,)).fetchone(), "Course")
        if any(h.hole_no > c["holes"] for h in body):
            raise HTTPException(422, f"This course has {c['holes']} holes.")
        for h in body:
            conn.execute("""INSERT INTO golf_holes (course_id, hole_no, par, stroke_index) VALUES (%s, %s, %s, %s)
                            ON CONFLICT (course_id, hole_no) DO UPDATE SET par = EXCLUDED.par, stroke_index = EXCLUDED.stroke_index""",
                         (course_id, h.hole_no, h.par, h.stroke_index))
        return course_detail(conn, course_id)


class TeeFields(BaseModel):
    colour: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    gender: str | None = Field(None, pattern=_lit(GENDERS))
    rating: float | None = Field(None, ge=25, le=85)
    slope: int | None = Field(None, ge=55, le=155)
    position: int | None = Field(None, ge=0, le=50)
    lengths: dict[int, int | None] | None = None


class TeeIn(TeeFields):
    name: str = Field(min_length=1, max_length=40)


class TeePatch(TeeFields):
    name: str | None = Field(None, min_length=1, max_length=40)


def _lengths(conn, tee_id: int, lengths: dict):
    for no, m in lengths.items():
        if not 1 <= int(no) <= 18 or (m is not None and not 30 <= m <= 800):
            raise HTTPException(422, "A hole's length is 30 to 800 metres.")
        if m is None:
            conn.execute("DELETE FROM golf_hole_lengths WHERE tee_id = %s AND hole_no = %s", (tee_id, no))
        else:
            conn.execute("""INSERT INTO golf_hole_lengths (tee_id, hole_no, metres) VALUES (%s, %s, %s)
                            ON CONFLICT (tee_id, hole_no) DO UPDATE SET metres = EXCLUDED.metres""", (tee_id, no, m))


@router.post("/golf/courses/{course_id}/tees", status_code=201)
def add_tee(course_id: int, body: TeeIn):
    data = tidy_text({k: v for k, v in body.model_dump(exclude={"lengths"}).items() if v is not None}, required=("name",))
    with db() as conn:
        found(conn.execute("SELECT 1 FROM golf_courses WHERE course_id = %s", (course_id,)).fetchone(), "Course")
        tee_id = insert_row(conn, "golf_tees", {**data, "course_id": course_id}, "tee_id")
        _lengths(conn, tee_id, body.lengths or {})
        return course_detail(conn, course_id)


@router.patch("/golf/tees/{tee_id}")
def update_tee(tee_id: int, body: TeePatch):
    data = tidy_text(body.model_dump(exclude_unset=True, exclude={"lengths"}), required=("name",))
    _required(data, "name", "gender", "position")
    with db() as conn:
        t = found(conn.execute("SELECT course_id FROM golf_tees WHERE tee_id = %s", (tee_id,)).fetchone(), "Tee")
        update_row(conn, "golf_tees", "tee_id", tee_id, data)
        if body.lengths is not None:
            _lengths(conn, tee_id, body.lengths)
        return course_detail(conn, t["course_id"])


@router.delete("/golf/tees/{tee_id}", status_code=204)
def delete_tee(tee_id: int):
    """Remove a set of tees; rounds played from them keep their scores (without its rating: no differential)."""
    with db() as conn:
        found(conn.execute("DELETE FROM golf_tees WHERE tee_id = %s RETURNING tee_id", (tee_id,)).fetchone(), "Tee")
    return Response(status_code=204)


# ---------------------------------------------------------------- the bag

class ClubFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(CLUB_KINDS))
    loft: float | None = Field(None, ge=0, le=70)
    carry_m: int | None = Field(None, ge=1, le=400)
    brand: str | None = Field(None, max_length=80)
    in_bag: bool | None = None
    position: int | None = Field(None, ge=0, le=100)
    notes: str | None = Field(None, max_length=2000)


class ClubIn(ClubFields):
    name: str = Field(min_length=1, max_length=40)
    kind: str = Field(pattern=_lit(CLUB_KINDS))


class ClubPatch(ClubFields):
    name: str | None = Field(None, min_length=1, max_length=40)


def clubs(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM golf_clubs ORDER BY NOT in_bag, position, loft NULLS LAST, club_id").fetchall()
    measured = golf_scores.club_distances(conn)
    for c in rows:
        c["measured"] = measured.get(c["club_id"])
    return rows


@router.get("/golf/clubs")
def list_clubs():
    with db() as conn:
        return clubs(conn)


@router.post("/golf/clubs", status_code=201)
def add_club(body: ClubIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    with db() as conn:
        if "position" not in data:
            data["position"] = conn.execute("SELECT COALESCE(max(position) + 1, 0) AS p FROM golf_clubs").fetchone()["p"]
        insert_row(conn, "golf_clubs", data, "club_id")
        return clubs(conn)


@router.post("/golf/clubs/standard-bag", status_code=201)
def standard_bag():
    """A typical set of clubs to start from (an empty bag only) - then edit the carries to yours."""
    with db() as conn:
        if conn.execute("SELECT 1 FROM golf_clubs LIMIT 1").fetchone():
            raise HTTPException(409, "Your bag already has clubs.")
        for i, (name, kind, loft, carry) in enumerate(STANDARD_BAG):
            insert_row(conn, "golf_clubs", {"name": name, "kind": kind, "loft": loft, "carry_m": carry, "position": i}, "club_id")
        return clubs(conn)


@router.patch("/golf/clubs/{club_id}")
def update_club(club_id: int, body: ClubPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "kind", "in_bag", "position")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM golf_clubs WHERE club_id = %s", (club_id,)).fetchone(), "Club")
        update_row(conn, "golf_clubs", "club_id", club_id, data)
        return clubs(conn)


@router.delete("/golf/clubs/{club_id}", status_code=204)
def delete_club(club_id: int):
    """Remove a club; shots hit with it stay (with no club)."""
    with db() as conn:
        found(conn.execute("DELETE FROM golf_clubs WHERE club_id = %s RETURNING club_id", (club_id,)).fetchone(), "Club")
    return Response(status_code=204)


# ---------------------------------------------------------------- practice

class PracticeFields(BaseModel):
    practiced_on: date | None = None
    minutes: int | None = Field(None, ge=1, le=600)
    balls: int | None = Field(None, ge=1, le=2000)
    focus: str | None = Field(None, max_length=200)
    drill: str | None = Field(None, max_length=120)
    made: int | None = Field(None, ge=0, le=1000)
    attempts: int | None = Field(None, ge=1, le=1000)
    notes: str | None = Field(None, max_length=5000)


class PracticeIn(PracticeFields):
    kind: str = Field(pattern=_lit(PRACTICE_KINDS))


class PracticePatch(PracticeFields):
    kind: str | None = Field(None, pattern=_lit(PRACTICE_KINDS))


@router.get("/golf/practice")
def list_practice(limit: int = Query(200, ge=1, le=2000)):
    """Practice sessions, newest first, with the totals this year and each drill's best and latest score."""
    with db() as conn:
        rows = conn.execute("SELECT * FROM golf_practice ORDER BY practiced_on DESC, practice_id DESC LIMIT %s", (limit,)).fetchall()
        year = conn.execute("""SELECT count(*)::int AS sessions, COALESCE(sum(minutes), 0)::int AS minutes,
                                      COALESCE(sum(balls), 0)::int AS balls
                               FROM golf_practice WHERE practiced_on >= date_trunc('year', current_date)""").fetchone()
        kinds = conn.execute("""SELECT kind, count(*)::int AS sessions, COALESCE(sum(minutes), 0)::int AS minutes
                                FROM golf_practice WHERE practiced_on >= current_date - 90 GROUP BY kind
                                ORDER BY minutes DESC""").fetchall()
        drills = conn.execute("""SELECT drill, count(*)::int AS times,
                                        max(round(100.0 * made / attempts))::int AS best_pct,
                                        (array_agg(round(100.0 * made / attempts)::int ORDER BY practiced_on DESC, practice_id DESC))[1] AS last_pct,
                                        (array_agg(made || '/' || attempts ORDER BY practiced_on DESC, practice_id DESC))[1] AS last
                                 FROM golf_practice WHERE drill IS NOT NULL AND made IS NOT NULL
                                 GROUP BY drill ORDER BY max(practiced_on) DESC""").fetchall()
        return {"sessions": rows, "year": year, "kinds": kinds, "drills": drills}


@router.post("/golf/practice", status_code=201)
def add_practice(body: PracticeIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
    with db() as conn:
        pid = insert_row(conn, "golf_practice", data, "practice_id")
        return conn.execute("SELECT * FROM golf_practice WHERE practice_id = %s", (pid,)).fetchone()


@router.patch("/golf/practice/{practice_id}")
def update_practice(practice_id: int, body: PracticePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    _required(data, "kind", "practiced_on")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM golf_practice WHERE practice_id = %s", (practice_id,)).fetchone(), "Practice session")
        update_row(conn, "golf_practice", "practice_id", practice_id, data)
        return conn.execute("SELECT * FROM golf_practice WHERE practice_id = %s", (practice_id,)).fetchone()


@router.delete("/golf/practice/{practice_id}", status_code=204)
def delete_practice(practice_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM golf_practice WHERE practice_id = %s RETURNING practice_id", (practice_id,)).fetchone(), "Practice session")
    return Response(status_code=204)
