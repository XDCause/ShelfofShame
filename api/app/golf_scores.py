"""Golf rounds scored (golf.py, golf_rounds.py): each hole's strokes received, Stableford points, net double bogey, green in
regulation...; a round's totals and stats; the handicap estimate and its history; stats over many rounds; club
distances from the shots you marked. The sums themselves are in golfmath.py.
"""
from statistics import median

from . import golfmath as gm

NINE = {"18": range(1, 19), "front": range(1, 10), "back": range(10, 19)}
TEAM = {"Ambrose"}           # a team score: not yours, so not for a handicap


def settings(conn) -> dict:
    return conn.execute("SELECT official_handicap, official_as_of, allowance, target_handicap, home_course_id "
                        "FROM golf_settings WHERE id = 1").fetchone()


def played(r: dict, course_holes: int) -> list[int]:
    nos = list(NINE[r["holes"]])
    return [n for n in nos if n <= course_holes]


def course_holes(conn, course_id: int, tee_id: int | None, with_map: bool = False) -> list[dict]:
    return conn.execute(
        f"""SELECT h.hole_no, h.par, h.stroke_index, l.metres{', h.map' if with_map else ''}
            FROM golf_holes h LEFT JOIN golf_hole_lengths l ON l.tee_id = %s AND l.hole_no = h.hole_no
            WHERE h.course_id = %s ORDER BY h.hole_no""", (tee_id, course_id)).fetchall()


# ---------------------------------------------------------------- one round

def score(r: dict, holes: list[dict], scores: dict, shots: dict, allowance) -> dict:
    """r: the round (with its tee's rating / slope and the course's hole count); holes: course_holes(); scores:
    {hole_no: golf_round_holes row}; shots: {hole_no: [shot rows in order]}. -> {holes: [...], totals, stats, sg}"""
    nos = played(r, r["course_holes"])
    mine = [h for h in holes if h["hole_no"] in nos]
    nine = len(nos) == 9
    par = sum(h["par"] for h in mine)
    rating = r.get("rating")
    rating = (float(rating) / 2 if nine and r["course_holes"] == 18 else float(rating)) if rating is not None else None
    daily = r["daily_handicap"]
    nine_si = [h["stroke_index"] for h in mine] if nine and all(h["stroke_index"] for h in mine) else None
    rows, sg_holes = [], []
    for h in mine:
        s = scores.get(h["hole_no"]) or {}
        got = gm.received(daily, h["stroke_index"], nine_si) if h["stroke_index"] else 0
        strokes = s.get("strokes")
        entered = strokes is not None or s.get("picked_up")
        putts = s.get("putts")
        gir = strokes - putts <= h["par"] - 2 if strokes is not None and putts is not None else None
        hole_shots = shots.get(h["hole_no"], [])
        green = (h.get("map") or {}).get("green")
        sg = gm.hole_strokes_gained(h["par"], hole_shots, gm.centre(green) if green else None, putts,
                                    s.get("first_putt_m"), s.get("penalties") or 0, strokes) if entered else None
        if sg:
            sg_holes.append(sg)
        rows.append({
            "hole_no": h["hole_no"], "par": h["par"], "stroke_index": h["stroke_index"], "metres": h.get("metres"),
            "received": got, "strokes": strokes, "putts": putts, "fairway": s.get("fairway"),
            "penalties": s.get("penalties") or 0, "sand": s.get("sand") or 0, "first_putt_m": s.get("first_putt_m"),
            "picked_up": bool(s.get("picked_up")), "entered": bool(entered),
            "points": gm.stableford(strokes, h["par"], got) if entered else None,
            "adjusted": gm.adjusted(strokes, h["par"], got) if entered else None,
            "to_par": strokes - h["par"] if strokes is not None else None,
            "gir": gir, "shots": len(hole_shots), "sg": sg, "map": h.get("map"),
        })
    done = [x for x in rows if x["entered"]]
    complete = bool(rows) and len(done) == len(rows)
    gross = sum(x["strokes"] for x in rows) if complete and all(x["strokes"] is not None for x in rows) else None
    ags = sum(x["adjusted"] for x in rows) if complete else None
    diff = None
    if (complete and r["counts"] and r["format"] not in TEAM and r.get("rating") is not None and r.get("slope")):
        d = gm.differential(ags, rating, r["slope"])
        diff = gm.nine_to_18(d, r.get("handicap")) if nine else d
    so_far = [x for x in done if x["strokes"] is not None]
    totals = {
        "par": par, "holes": len(rows), "entered": len(done), "complete": complete,
        "gross": gross, "to_par": gross - par if gross is not None else None,
        "to_par_so_far": sum(x["strokes"] - x["par"] for x in so_far) if so_far else None,
        "strokes_so_far": sum(x["strokes"] for x in so_far),
        "points": sum(x["points"] or 0 for x in done), "net": gross - daily if gross is not None and daily is not None else None,
        "adjusted_gross": ags, "differential": diff, "rating": rating, "nine": nine,
    }
    return {"holes": rows, "totals": totals, "stats": hole_stats(rows), "sg": sg_sum(sg_holes)}


def hole_stats(rows: list[dict]) -> dict:
    """Counts over holes (rows from score()): add these up over rounds, then per_round() / rates()."""
    st = dict.fromkeys(("holes", "putt_holes", "putts", "fairway_chances", "fairways", "left", "right", "gir_chances",
                        "gir", "gir_putts", "scramble_chances", "scrambles", "sand_chances", "sand_saves", "three_putts",
                        "penalties", "eagles", "birdies", "pars", "bogeys", "doubles", "worse",
                        "par3_n", "par3_sum", "par4_n", "par4_sum", "par5_n", "par5_sum"), 0)
    for x in rows:
        if not x["entered"]:
            continue
        st["holes"] += 1
        st["penalties"] += x["penalties"]
        if x["fairway"] and x["par"] >= 4:
            st["fairway_chances"] += 1
            st["fairways"] += x["fairway"] == "hit"
            st["left"] += x["fairway"] == "left"
            st["right"] += x["fairway"] == "right"
        if x["putts"] is not None:
            st["putt_holes"] += 1
            st["putts"] += x["putts"]
            st["three_putts"] += x["putts"] >= 3
        if x["gir"] is not None:
            st["gir_chances"] += 1
            st["gir"] += x["gir"]
            st["gir_putts"] += x["putts"] if x["gir"] else 0
            if not x["gir"]:
                st["scramble_chances"] += 1
                st["scrambles"] += x["strokes"] <= x["par"]
        if x["sand"] and x["strokes"] is not None:
            st["sand_chances"] += 1
            st["sand_saves"] += x["strokes"] <= x["par"]
        if x["strokes"] is None:
            st["worse"] += 1
            continue
        d = x["strokes"] - x["par"]
        st["eagles" if d <= -2 else "birdies" if d == -1 else "pars" if d == 0 else "bogeys" if d == 1 else
           "doubles" if d == 2 else "worse"] += 1
        p = min(5, x["par"])
        st[f"par{p}_n"] += 1
        st[f"par{p}_sum"] += x["strokes"]
    return st


def add(a: dict, b: dict) -> dict:
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


def rates(st: dict) -> dict:
    """Counts -> the numbers people quote: % of fairways and greens, putts and three-putts and penalties a round
    (per 18 holes), scrambling and sand saves %, average score on par 3s / 4s / 5s."""
    def pct(n, d):
        return round(100 * n / d, 1) if d else None

    def per18(n, holes):
        return round(18 * n / holes, 1) if holes else None
    return {
        "holes": st.get("holes", 0),
        "fairways": pct(st.get("fairways", 0), st.get("fairway_chances", 0)),
        "missed_left": pct(st.get("left", 0), st.get("fairway_chances", 0)),
        "missed_right": pct(st.get("right", 0), st.get("fairway_chances", 0)),
        "gir": pct(st.get("gir", 0), st.get("gir_chances", 0)),
        "putts": per18(st.get("putts", 0), st.get("putt_holes", 0)),
        "putts_per_gir": round(st["gir_putts"] / st["gir"], 2) if st.get("gir") else None,
        "scrambling": pct(st.get("scrambles", 0), st.get("scramble_chances", 0)),
        "sand_saves": pct(st.get("sand_saves", 0), st.get("sand_chances", 0)),
        "three_putts": per18(st.get("three_putts", 0), st.get("putt_holes", 0)),
        "penalties": per18(st.get("penalties", 0), st.get("holes", 0)),
        "par3": round(st["par3_sum"] / st["par3_n"], 2) if st.get("par3_n") else None,
        "par4": round(st["par4_sum"] / st["par4_n"], 2) if st.get("par4_n") else None,
        "par5": round(st["par5_sum"] / st["par5_n"], 2) if st.get("par5_n") else None,
        "kinds": {k: st.get(k, 0) for k in ("eagles", "birdies", "pars", "bogeys", "doubles", "worse")},
    }


def sg_sum(holes: list[dict]) -> dict:
    """Strokes gained per category over holes: {cat: {total, holes, per18}}."""
    out = {}
    for cat in ("off_tee", "approach", "around_green", "putting"):
        vals = [h[cat] for h in holes if h.get(cat) is not None]
        out[cat] = {"total": round(sum(vals), 2), "holes": len(vals),
                    "per18": round(18 * sum(vals) / len(vals), 2) if vals else None}
    return out


def sg_merge(parts: list[dict]) -> dict:
    out = {}
    for cat in ("off_tee", "approach", "around_green", "putting"):
        total = sum(p[cat]["total"] for p in parts)
        n = sum(p[cat]["holes"] for p in parts)
        out[cat] = {"total": round(total, 2), "holes": n, "per18": round(18 * total / n, 2) if n else None}
    return out


# ---------------------------------------------------------------- many rounds

ROUND_SELECT = """SELECT r.*, c.name AS course_name, c.holes AS course_holes, c.lat, c.lon,
       t.name AS tee_name, t.colour AS tee_colour, t.rating, t.slope
FROM golf_rounds r JOIN golf_courses c USING (course_id) LEFT JOIN golf_tees t ON t.tee_id = r.tee_id"""


def load(conn, where: str = "TRUE", params=(), with_map: bool = False) -> list[dict]:
    """Rounds (newest first) with everything score() works out, in four queries whatever the number of rounds."""
    rounds = conn.execute(f"{ROUND_SELECT} WHERE {where} ORDER BY r.played_on DESC, r.started_at DESC", params).fetchall()
    if not rounds:
        return []
    ids = [r["round_id"] for r in rounds]
    courses = list({r["course_id"] for r in rounds})
    hole_rows = conn.execute(
        f"""SELECT h.course_id, h.hole_no, h.par, h.stroke_index, {'h.map' if with_map else "jsonb_build_object('green', h.map->'green') AS map"}
            FROM golf_holes h WHERE h.course_id = ANY(%s) ORDER BY h.hole_no""", (courses,)).fetchall()
    lengths = conn.execute("""SELECT l.tee_id, l.hole_no, l.metres FROM golf_hole_lengths l
                              WHERE l.tee_id = ANY(%s)""", ([r["tee_id"] for r in rounds if r["tee_id"]],)).fetchall()
    score_rows = conn.execute("SELECT * FROM golf_round_holes WHERE round_id = ANY(%s)", (ids,)).fetchall()
    shot_rows = conn.execute("SELECT * FROM golf_shots WHERE round_id = ANY(%s) ORDER BY round_id, hole_no, seq",
                             (ids,)).fetchall()
    by_course, metres, scores, shots = {}, {}, {}, {}
    for h in hole_rows:
        by_course.setdefault(h["course_id"], []).append(h)
    for m in lengths:
        metres[(m["tee_id"], m["hole_no"])] = m["metres"]
    for s in score_rows:
        scores.setdefault(s["round_id"], {})[s["hole_no"]] = s
    for s in shot_rows:
        shots.setdefault(s["round_id"], {}).setdefault(s["hole_no"], []).append(s)
    allowance = settings(conn)["allowance"]
    out = []
    for r in rounds:
        holes = [{**h, "metres": metres.get((r["tee_id"], h["hole_no"]))} for h in by_course.get(r["course_id"], [])]
        # (score()'s "holes" - the hole rows - takes the round's own "holes" name: that stays as hole_set)
        out.append({**r, **score(r, holes, scores.get(r["round_id"], {}), shots.get(r["round_id"], {}), allowance),
                    "hole_set": r["holes"], "allowance": allowance})
    return out


def handicap(conn, rounds: list[dict] | None = None) -> dict:
    """The estimate (WHS, from your finished rounds), its history after each counting round, the official one you
    typed, and which is used (official first)."""
    if rounds is None:
        rounds = load(conn, "r.status = 'done'")
    counting = [r for r in rounds if r["status"] == "done" and r["totals"]["differential"] is not None]
    diffs = [(r["round_id"], r["totals"]["differential"]) for r in counting]           # newest first
    now = gm.handicap_index(diffs)
    history = []
    for i in range(len(counting) - 1, -1, -1):
        h = gm.handicap_index(diffs[i:])
        if h:
            history.append({"day": counting[i]["played_on"], "index": h["index"], "round_id": counting[i]["round_id"]})
    s = settings(conn)
    official = float(s["official_handicap"]) if s["official_handicap"] is not None else None
    estimate = now["index"] if now else None
    return {
        "estimate": estimate, "official": official, "official_as_of": s["official_as_of"],
        "current": official if official is not None else estimate,
        "source": "official" if official is not None else "estimate" if estimate is not None else None,
        "used": now["used"] if now else [], "of": now["of"] if now else len(diffs), "best": now["best"] if now else None,
        "counting": len(diffs), "history": history, "target": float(s["target_handicap"]) if s["target_handicap"] is not None else None,
        "allowance": float(s["allowance"]),
    }


def summarise(rounds: list[dict]) -> dict:
    """Stats over finished rounds: counts added up, then rates(), strokes gained and 'plays like'."""
    st, sgs = {}, []
    for r in rounds:
        st = add(st, r["stats"])
        sgs.append(r["sg"])
    out = rates(st) if st else rates({})
    out["sg"] = sg_merge(sgs) if sgs else sg_merge([])
    out["plays_like"] = {k: gm.plays_like(k, out[k]) for k in ("fairways", "gir", "putts", "scrambling", "three_putts", "penalties")
                         if out.get(k) is not None}
    full = [r for r in rounds if r["totals"]["complete"] and not r["totals"]["nine"]]
    grosses = [r["totals"]["gross"] for r in full if r["totals"]["gross"] is not None]
    points = [r["totals"]["points"] for r in full if r["format"] == "Stableford"]
    out["rounds"] = len(rounds)
    out["average"] = round(sum(grosses) / len(grosses), 1) if grosses else None
    out["best"] = min(grosses) if grosses else None
    out["average_points"] = round(sum(points) / len(points), 1) if points else None
    out["best_points"] = max(points) if points else None
    return out


def club_distances(conn) -> dict:
    """Each club's distances: from a marked shot to the next one on the same hole (the ball's resting place)."""
    rows = conn.execute("""SELECT s.club_id, s.lat, s.lon, n.lat AS next_lat, n.lon AS next_lon, s.lie
                           FROM golf_shots s JOIN golf_shots n ON n.round_id = s.round_id AND n.hole_no = s.hole_no
                                AND n.seq = s.seq + 1
                           WHERE s.club_id IS NOT NULL""").fetchall()
    found = {}
    for r in rows:
        d = gm.metres_between((r["lat"], r["lon"]), (r["next_lat"], r["next_lon"]))
        if 1 <= d <= 400:
            found.setdefault(r["club_id"], []).append(d)
    out = {}
    for club, ds in found.items():
        ds.sort()
        out[club] = {"shots": len(ds), "average": round(sum(ds) / len(ds)), "median": round(median(ds)),
                     "longest": round(ds[-1]), "short": round(ds[len(ds) // 4]), "long": round(ds[(3 * len(ds)) // 4])}
    return out
