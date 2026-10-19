"""Precision shooting: sessions at the range, the groups in them, your DOPE and the dashboard (rifles, ammo,
ranges and settings are in shooting.py; the arithmetic in shotmath.py).

    GET  /shooting/sessions?year=&rifle_id=&kind=&q=   newest first, with rounds, best group, score
    POST /shooting/sessions                 a session (and its groups, if sent)
    GET / PATCH / DELETE /shooting/sessions/{id}       with every group worked out (MOA / MIL, velocities, a
                                            zeroing suggestion from where it hit)
    POST /shooting/sessions/{id}/groups; PATCH / DELETE /shooting/groups/{id} (+ /photo: the target)
                                            (shots, photos and videos: shooting_shots.py)
    GET  /shooting/dope?rifle_id=&ammo_id=  your DOPE card: what your groups confirmed, what you entered, and
                                            estimates between them (never past the furthest you've confirmed)
    POST /shooting/dope; DELETE /shooting/dope/{id}
    GET  /shooting/summary                  the dashboard
A group's size is centre to centre of its two widest shots, in mm; where it hit (up / right of the aim, mm) and
what was dialled are in the rifle's scope unit.
"""
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from . import shotmath
from .db import db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes
from .shooting import AMMO_SELECT, POSITIONS, SESSION_KINDS, SESSION_ROUNDS, _lit, ammo_row, list_rifles, settings

router = APIRouter(prefix="/api", tags=["shooting"])


class GroupFields(BaseModel):
    distance: int | None = Field(None, ge=1, le=5000)
    unit: str | None = Field(None, pattern="^(m|yd)$")
    shots: int | None = Field(None, ge=1, le=1000)
    size_mm: float | None = Field(None, ge=0, le=100000)
    up_mm: float | None = Field(None, ge=-100000, le=100000)
    right_mm: float | None = Field(None, ge=-100000, le=100000)
    elevation: float | None = Field(None, ge=-1000, le=1000)
    windage: float | None = Field(None, ge=-1000, le=1000)
    position: str | None = Field(None, pattern=_lit(POSITIONS))
    score: float | None = Field(None, ge=0, le=100000)
    x_count: int | None = Field(None, ge=0, le=1000)
    velocities: list[float] | None = Field(None, max_length=200)
    confirms_dope: bool | None = None
    target: str | None = Field(None, max_length=120)
    hits: int | None = Field(None, ge=0, le=1000)
    notes: str | None = Field(None, max_length=5000)


class GroupIn(GroupFields):
    distance: int = Field(ge=1, le=5000)


class SessionFields(BaseModel):
    shot_on: date | None = None
    kind: str | None = Field(None, pattern=_lit(SESSION_KINDS))
    range_id: int | None = None
    rifle_id: int | None = None
    ammo_id: int | None = None
    match_name: str | None = Field(None, max_length=200)
    finish: str | None = Field(None, max_length=60)
    rounds: int | None = Field(None, ge=0, le=100000)
    temp_c: float | None = Field(None, ge=-40, le=60)
    wind_kmh: float | None = Field(None, ge=0, le=200)
    wind_from: str | None = Field(None, max_length=40)
    light: str | None = Field(None, max_length=60)
    notes: str | None = Field(None, max_length=10000)


class SessionIn(SessionFields):
    groups: list[GroupIn] = Field(default_factory=list, max_length=100)


SESSION_SELECT = f"""
SELECT s.session_id, s.shot_on, s.kind, s.range_id, s.rifle_id, s.ammo_id, s.match_name, s.finish, s.rounds AS rounds_entered,
       {SESSION_ROUNDS}::int AS rounds, s.temp_c::float8 AS temp_c, s.wind_kmh::float8 AS wind_kmh, s.wind_from, s.light, s.notes,
       s.created_at, rg.name AS range_name, rg.counts_for_club, r.name AS rifle_name, COALESCE(r.scope_unit, 'MOA') AS scope_unit,
       r.click::float8 AS click, a.name AS ammo_name,
       (SELECT count(*) FROM shooting_groups g WHERE g.session_id = s.session_id)::int AS groups,
       (SELECT sum(g.score)::float8 FROM shooting_groups g WHERE g.session_id = s.session_id) AS score,
       (SELECT sum(g.x_count)::int FROM shooting_groups g WHERE g.session_id = s.session_id) AS x_count,
       (SELECT sum(g.hits)::int FROM shooting_groups g WHERE g.session_id = s.session_id) AS hits,
       (SELECT sum(g.shots)::int FROM shooting_groups g WHERE g.session_id = s.session_id AND g.hits IS NOT NULL) AS hit_shots,
       (SELECT min(g.size_mm / (CASE g.unit WHEN 'yd' THEN g.distance * 0.9144 ELSE g.distance END * {shotmath.MM_PER_MOA_AT_100M} / 100))::float8
        FROM shooting_groups g WHERE g.session_id = s.session_id AND g.size_mm IS NOT NULL AND COALESCE(g.shots, 3) >= 3) AS best_moa,
       (SELECT '/api/shooting/groups/' || g.group_id || '/photo?v=' || (extract(epoch FROM g.photo_updated) * 1000)::bigint
        FROM shooting_groups g WHERE g.session_id = s.session_id AND g.photo IS NOT NULL ORDER BY g.group_id LIMIT 1) AS photo_url
FROM shooting_sessions s
LEFT JOIN shooting_ranges rg ON rg.range_id = s.range_id
LEFT JOIN rifles r ON r.rifle_id = s.rifle_id
LEFT JOIN ammo a ON a.ammo_id = s.ammo_id"""

GROUP_SELECT = """
SELECT g.group_id, g.session_id, g.distance, g.unit, g.shots, g.size_mm::float8 AS size_mm, g.up_mm::float8 AS up_mm,
       g.right_mm::float8 AS right_mm, g.elevation::float8 AS elevation, g.windage::float8 AS windage, g.position,
       g.score::float8 AS score, g.x_count, g.velocities::float8[] AS velocities, g.confirms_dope, g.notes, g.target, g.hits,
       s.shot_on, s.rifle_id, s.ammo_id, s.wind_kmh::float8 AS wind_kmh, COALESCE(r.scope_unit, 'MOA') AS scope_unit,
       r.click::float8 AS click,
       CASE WHEN g.photo IS NOT NULL THEN '/api/shooting/groups/' || g.group_id || '/photo?v='
            || (extract(epoch FROM g.photo_updated) * 1000)::bigint END AS photo_url
FROM shooting_groups g JOIN shooting_sessions s ON s.session_id = g.session_id LEFT JOIN rifles r ON r.rifle_id = s.rifle_id"""


def decorate(g: dict) -> dict:
    """A group worked out: metres, size as MOA / MIL / in the scope's unit, chronograph numbers, and - from where
    it hit - what to dial to bring it to the aim point."""
    m = shotmath.metres(g["distance"], g["unit"])
    unit = g["scope_unit"]
    g["metres"] = round(m, 1)
    g["moa"] = _r(shotmath.moa(g["size_mm"], m))
    g["mil"] = _r(shotmath.mil(g["size_mm"], m))
    g["angle"] = g["mil"] if unit == "MIL" else g["moa"]
    g["velocity"] = shotmath.velocity_stats(g["velocities"])
    g["hit_rate"] = round(100 * g["hits"] / g["shots"]) if g["hits"] is not None and g["shots"] else None
    called = [s["hit"] for s in g.get("shot_list") or [] if s["hit"] is not None]
    g["best_streak"] = max((len(run) for run in "".join("h" if h else "m" for h in called).split("m")), default=0) if called else None
    g["correction"] = None
    # shot by shot: mean radius and spread from where the (non-flyer) shots landed
    placed = [(s["x_mm"], s["y_mm"]) for s in g.get("shot_list") or [] if s["x_mm"] is not None and not s["flyer"]]
    stats = shotmath.group_stats(placed) if len(placed) >= 2 else None
    g["spread"] = stats and {**stats, "mean_radius": _r(shotmath.angle(stats["mean_radius_mm"], m, unit)),
                             "flyers": sum(1 for s in g["shot_list"] if s["flyer"])}
    if g["up_mm"] or g["right_mm"]:
        up = shotmath.angle(g["up_mm"] or 0, m, unit)
        right = shotmath.angle(g["right_mm"] or 0, m, unit)
        click = g["click"] or (0.1 if unit == "MIL" else 0.25)
        moves = [f"{abs(up):.2f} {unit} {'down' if up > 0 else 'up'} ({round(abs(up) / click)} clicks)" if abs(up) >= click / 2 else None,
                 f"{abs(right):.2f} {unit} {'left' if right > 0 else 'right'} ({round(abs(right) / click)} clicks)"
                 if abs(right) >= click / 2 else None]
        g["correction"] = "Dial " + " and ".join(x for x in moves if x) if any(moves) else "On the aim point"
    return g


def _r(v, places=2):
    return None if v is None else round(v, places)


def fetch_session(conn, session_id: int) -> dict:
    s = found(conn.execute(SESSION_SELECT + " WHERE s.session_id = %s", (session_id,)).fetchone(), "Session")
    from .shooting_shots import media_for, shots_by_group
    groups = conn.execute(GROUP_SELECT + " WHERE g.session_id = %s ORDER BY g.group_id", (session_id,)).fetchall()
    shots = shots_by_group(conn, [g["group_id"] for g in groups])
    s["groups_list"] = [decorate({**g, "shot_list": shots[g["group_id"]]}) for g in groups]
    s["media"] = media_for(conn, session_id)
    s["best_moa"] = _r(s["best_moa"])
    return s


def _group_data(body: BaseModel, partial: bool) -> dict:
    data = tidy_text(body.model_dump(exclude_unset=partial), required=())
    if not partial:
        data = {k: v for k, v in data.items() if v is not None}
    if "velocities" in data:
        data["velocities"] = [round(v, 1) for v in data["velocities"] or [] if 0 < v < 3000]
    return data


@router.get("/shooting/sessions")
def list_sessions(year: int | None = Query(None, ge=1900, le=3000), rifle_id: int | None = None, kind: str | None = None,
                  q: str | None = Query(None, max_length=100)):
    with db() as conn:
        rows = conn.execute(SESSION_SELECT + """ WHERE (%(y)s::int IS NULL OR extract(year FROM s.shot_on) = %(y)s)
            AND (%(rifle)s::int IS NULL OR s.rifle_id = %(rifle)s) AND (%(kind)s::text IS NULL OR s.kind = %(kind)s)
            AND (%(q)s::text IS NULL OR concat_ws(' ', s.notes, s.match_name, rg.name, r.name, a.name) ILIKE '%%' || %(q)s || '%%')
            ORDER BY s.shot_on DESC, s.session_id DESC""",
                            {"y": year, "rifle": rifle_id, "kind": kind, "q": (q or "").strip() or None}).fetchall()
    for s in rows:
        s["best_moa"] = _r(s["best_moa"])
    return rows


@router.post("/shooting/sessions", status_code=201)
def add_session(body: SessionIn):
    groups = body.groups
    data = tidy_text({k: v for k, v in body.model_dump(exclude={"groups"}).items() if v is not None}, required=())
    data.setdefault("kind", "Practice")          # (an INSERT needs at least one column; the date defaults to today)
    with db() as conn:
        session_id = insert_row(conn, "shooting_sessions", data, "session_id")
        for g in groups:
            insert_row(conn, "shooting_groups", {**_group_data(g, False), "session_id": session_id}, "group_id")
        return fetch_session(conn, session_id)


@router.get("/shooting/sessions/{session_id}")
def get_session(session_id: int):
    with db() as conn:
        return fetch_session(conn, session_id)


@router.patch("/shooting/sessions/{session_id}")
def update_session(session_id: int, body: SessionFields):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    for required in ("shot_on", "kind"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        fetch_session(conn, session_id)
        update_row(conn, "shooting_sessions", "session_id", session_id, data)
        return fetch_session(conn, session_id)


@router.delete("/shooting/sessions/{session_id}", status_code=204)
def delete_session(session_id: int):
    """Remove a session: its groups, shots, photos and videos (their files too)."""
    from .volleyball import remove_file
    with db() as conn:
        files = [m["file_name"] for m in conn.execute("SELECT file_name FROM shooting_media WHERE session_id = %s AND file_name IS NOT NULL",
                                                      (session_id,)).fetchall()]
        found(conn.execute("DELETE FROM shooting_sessions WHERE session_id = %s RETURNING session_id", (session_id,)).fetchone(),
              "Session")
    for name in files:
        remove_file(name)
    return Response(status_code=204)


@router.post("/shooting/sessions/{session_id}/groups", status_code=201)
def add_group(session_id: int, body: GroupIn):
    with db() as conn:
        fetch_session(conn, session_id)
        insert_row(conn, "shooting_groups", {**_group_data(body, False), "session_id": session_id}, "group_id")
        return fetch_session(conn, session_id)


@router.patch("/shooting/groups/{group_id}")
def update_group(group_id: int, body: GroupFields):
    data = _group_data(body, True)
    for required in ("distance", "unit", "confirms_dope"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        g = found(conn.execute("SELECT session_id FROM shooting_groups WHERE group_id = %s", (group_id,)).fetchone(), "Group")
        update_row(conn, "shooting_groups", "group_id", group_id, data)
        return fetch_session(conn, g["session_id"])


@router.delete("/shooting/groups/{group_id}")
def delete_group(group_id: int):
    with db() as conn:
        g = found(conn.execute("DELETE FROM shooting_groups WHERE group_id = %s RETURNING session_id", (group_id,)).fetchone(), "Group")
        return fetch_session(conn, g["session_id"])


add_photo_routes(router, "/shooting/groups", "shooting_groups", "group_id", "Group")


# ---------------------------------------------------------------------------------------------
# How ammo groups in a rifle (the rifle's and the ammo's panels, the dashboard)
# ---------------------------------------------------------------------------------------------
def _performance(groups: list[dict], unit: str) -> dict:
    sized = [g for g in groups if g["angle"] is not None and (g["shots"] or 3) >= 3]
    vel = [g["velocity"] for g in groups if g["velocity"]]
    return {"groups": len(sized), "avg": _r(sum(g["angle"] for g in sized) / len(sized)) if sized else None,
            "best": _r(min(g["angle"] for g in sized)) if sized else None, "unit": unit,
            "velocity": _r(sum(v["avg"] for v in vel) / len(vel), 1) if vel else None,
            "sd": _r(sum(v["sd"] for v in vel) / len(vel), 1) if vel else None}


def ammo_in_rifle(conn, rifle_id: int, unit: str) -> list[dict]:
    rows = [decorate(g) for g in conn.execute(GROUP_SELECT + " WHERE s.rifle_id = %s", (rifle_id,)).fetchall()]
    names = {a["ammo_id"]: a["name"] for a in conn.execute("SELECT ammo_id, name FROM ammo").fetchall()}
    out = []
    for ammo_id in {g["ammo_id"] for g in rows}:
        mine = [g for g in rows if g["ammo_id"] == ammo_id]
        out.append({"ammo_id": ammo_id, "name": names.get(ammo_id, "Ammo not noted"), **_performance(mine, unit)})
    return sorted(out, key=lambda a: (a["avg"] is None, a["avg"] or 0))


def rifles_for_ammo(conn, ammo_id: int) -> list[dict]:
    rows = [decorate(g) for g in conn.execute(GROUP_SELECT + " WHERE s.ammo_id = %s", (ammo_id,)).fetchall()]
    names = {r["rifle_id"]: (r["name"], r["scope_unit"]) for r in conn.execute("SELECT rifle_id, name, scope_unit FROM rifles").fetchall()}
    out = []
    for rifle_id in {g["rifle_id"] for g in rows}:
        name, unit = names.get(rifle_id, ("Rifle not noted", "MOA"))
        out.append({"rifle_id": rifle_id, "name": name, **_performance([g for g in rows if g["rifle_id"] == rifle_id], unit)})
    return sorted(out, key=lambda a: (a["avg"] is None, a["avg"] or 0))


# ---------------------------------------------------------------------------------------------
# DOPE
# ---------------------------------------------------------------------------------------------
class DopeIn(BaseModel):
    rifle_id: int
    ammo_id: int | None = None
    distance: int = Field(ge=1, le=5000)
    unit: str = Field("m", pattern="^(m|yd)$")
    elevation: float = Field(ge=-1000, le=1000)
    wind10: float | None = Field(None, ge=-1000, le=1000)
    notes: str | None = Field(None, max_length=1000)


@router.get("/shooting/dope")
def dope(rifle_id: int, ammo_id: int | None = None):
    """The DOPE card for a rifle (and ammo): per distance, what your groups confirmed (the latest), else what you
    entered - and estimates between confirmed distances, marked as estimates."""
    with db() as conn:
        rifle = found(conn.execute("SELECT rifle_id, name, scope_unit, click::float8 AS click, zero_m FROM rifles WHERE rifle_id = %s",
                                   (rifle_id,)).fetchone(), "Rifle")
        groups = [decorate(g) for g in conn.execute(
            GROUP_SELECT + " WHERE s.rifle_id = %s AND (%s::int IS NULL OR s.ammo_id = %s) AND g.confirms_dope AND g.elevation IS NOT NULL "
            "ORDER BY s.shot_on DESC, g.group_id DESC", (rifle_id, ammo_id, ammo_id)).fetchall()]
        manual = conn.execute("SELECT dope_id, distance, unit, elevation::float8 AS elevation, wind10::float8 AS wind10, notes "
                              "FROM dope_rows WHERE rifle_id = %s AND (%s::int IS NULL OR ammo_id IS NULL OR ammo_id = %s)",
                              (rifle_id, ammo_id, ammo_id)).fetchall()
    rows = {}
    for d in manual:
        m = round(shotmath.metres(d["distance"], d["unit"]))
        rows[m] = {"m": m, "distance": d["distance"], "unit": d["unit"], "elevation": d["elevation"], "wind10": d["wind10"],
                   "source": "entered", "dope_id": d["dope_id"], "notes": d["notes"]}
    for g in reversed(groups):          # oldest first, so the latest confirmation wins
        m = round(g["metres"])
        wind10 = _r(g["windage"] * 10 / g["wind_kmh"]) if g["windage"] is not None and g["wind_kmh"] else None
        rows[m] = {"m": m, "distance": g["distance"], "unit": g["unit"], "elevation": g["elevation"],
                   "wind10": wind10 if wind10 is not None else rows.get(m, {}).get("wind10"), "source": "confirmed",
                   "on": g["shot_on"], "session_id": g["session_id"], "group_id": g["group_id"]}
    known = sorted(rows.values(), key=lambda r: r["m"])
    table = list(known)
    if len(known) >= 2:
        step = 25 if known[-1]["m"] <= 300 else 50
        for m in range(-(-known[0]["m"] // step) * step, known[-1]["m"] + 1, step):
            if m not in rows:
                table.append({"m": m, "distance": m, "unit": "m", "elevation": shotmath.estimate(known, m), "wind10": None,
                              "source": "estimate"})
    return {"rifle": rifle, "unit": rifle["scope_unit"], "rows": sorted(table, key=lambda r: r["m"])}


@router.post("/shooting/dope", status_code=201)
def add_dope(body: DopeIn):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM rifles WHERE rifle_id = %s", (body.rifle_id,)).fetchone(), "Rifle")
        insert_row(conn, "dope_rows", tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=()), "dope_id")
    return dope(body.rifle_id, body.ammo_id)


@router.delete("/shooting/dope/{dope_id}", status_code=204)
def delete_dope(dope_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM dope_rows WHERE dope_id = %s RETURNING dope_id", (dope_id,)).fetchone(), "DOPE row")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------------------------
@router.get("/shooting/summary")
def summary():
    rifles = list_rifles()
    with db() as conn:
        s = settings(conn)
        year = conn.execute("SELECT extract(year FROM current_date)::int AS y").fetchone()["y"]
        this_year = conn.execute(f"""SELECT count(*)::int AS sessions, COALESCE(sum({SESSION_ROUNDS}), 0)::int AS rounds,
            count(DISTINCT s.shot_on) FILTER (WHERE rg.counts_for_club)::int AS club_days,
            count(DISTINCT s.range_id)::int AS ranges, count(*) FILTER (WHERE s.kind = 'Match')::int AS matches
            FROM shooting_sessions s LEFT JOIN shooting_ranges rg ON rg.range_id = s.range_id
            WHERE extract(year FROM s.shot_on) = %s""", (year,)).fetchone()
        all_time = conn.execute(f"SELECT count(*)::int AS sessions, COALESCE(sum({SESSION_ROUNDS}), 0)::int AS rounds "
                                "FROM shooting_sessions s").fetchone()
        recent = conn.execute(SESSION_SELECT + " ORDER BY s.shot_on DESC, s.session_id DESC LIMIT 6").fetchall()
        groups_all = [decorate(g) for g in conn.execute(GROUP_SELECT + " WHERE extract(year FROM s.shot_on) = %s", (year,)).fetchall()]
        groups = [decorate(g) for g in conn.execute(GROUP_SELECT + " WHERE g.size_mm IS NOT NULL").fetchall()]
        months = conn.execute(f"""SELECT to_char(m, 'YYYY-MM') AS month,
                (SELECT count(*) FROM shooting_sessions s WHERE date_trunc('month', s.shot_on) = m)::int AS sessions,
                (SELECT COALESCE(sum({SESSION_ROUNDS}), 0) FROM shooting_sessions s WHERE date_trunc('month', s.shot_on) = m)::int AS rounds
            FROM generate_series(date_trunc('month', current_date) - interval '11 months', date_trunc('month', current_date),
                                 interval '1 month') m""").fetchall()
        matches = conn.execute(SESSION_SELECT + " WHERE s.kind = 'Match' ORDER BY s.shot_on DESC LIMIT 12").fetchall()
        ammo = [ammo_row(a) for a in conn.execute(AMMO_SELECT + " WHERE a.status = 'Have'").fetchall()]
        spend = conn.execute(f"""SELECT COALESCE(sum({SESSION_ROUNDS} * a.box_price / NULLIF(a.box_size, 0)), 0)::float8 AS spent
            FROM shooting_sessions s JOIN ammo a ON a.ammo_id = s.ammo_id WHERE extract(year FROM s.shot_on) = %s""", (year,)).fetchone()
    for r in recent + matches:
        r["best_moa"] = _r(r["best_moa"])
    # Best groups: the smallest (3+ shots, in MOA) at each distance you've shot
    best = {}
    for g in groups:
        if g["moa"] is None or (g["shots"] or 3) < 3:
            continue
        key = f"{g['distance']} {g['unit']}"
        if key not in best or g["moa"] < best[key]["moa"]:
            best[key] = g
    trend = {}
    for g in groups:
        if g["moa"] is not None and (g["shots"] or 3) >= 3:
            trend.setdefault(g["shot_on"].strftime("%Y-%m"), []).append(g["moa"])
    for m in months:
        sizes = trend.get(m["month"])
        m["avg_moa"] = _r(sum(sizes) / len(sizes)) if sizes else None
    rates = {}
    for g in groups_all:
        if g["hits"] is not None and g["shots"]:
            r = rates.setdefault(f"{g['distance']} {g['unit']}", {"label": f"{g['distance']} {g['unit']}", "m": g["metres"], "hits": 0, "shots": 0})
            r["hits"] += g["hits"]
            r["shots"] += g["shots"]
    hit_rates = sorted(({**r, "rate": round(100 * r["hits"] / r["shots"])} for r in rates.values()), key=lambda r: r["m"])
    return {
        "hit_rates": hit_rates,
        "year": year, "settings": s, "this_year": this_year, "all_time": all_time, "recent": recent,
        "bests": sorted(best.values(), key=lambda g: g["metres"]), "months": months, "matches": list(reversed(matches)),
        "rifles": [r for r in rifles if r["status"] == "In use"], "clean_due": [r for r in rifles if r["clean_due"]],
        "pta": [r for r in rifles if r["pta_applied"] and (not r["pta_approved"] or (r["status"] == "Wanted"))],
        "low_ammo": [a for a in ammo if a["low"]], "spent": round(spend["spent"], 2),
        "club_needed": s["club_shoots_needed"],
    }
