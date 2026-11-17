"""Golf's arithmetic (golf.py, golf_rounds.py): no database here, so every sum can be tested on its own.

    daily_handicap(index, slope, rating, par, allowance, nine)   Golf Australia: (index x slope / 113 + (rating - par)) x 0.93
    received(daily, si, holes_si)       strokes you get on a hole (stroke index; a 9-hole round ranks the nine's indexes)
    stableford(strokes, par, got)       points: 2 for a net par, 1 a net bogey... 0 for a pick-up
    adjusted(strokes, par, got)         net double bogey: the most a hole can count for a handicap
    differential(ags, rating, slope)    (113 / slope) x (adjusted gross - rating)
    handicap_index(diffs)               the World Handicap System's table: best 8 of the last 20 (fewer: fewer, adjusted)
    nine_to_18(d9, index)               a 9-hole differential + the expected one for the other nine (WHS 2024)
    expected(lie, metres)               strokes a tour pro needs to hole out from there (Broadie's baseline)
    plays_like(stat, value)             which handicap your stat looks like (rough amateur averages)
    metres_between(a, b)                two GPS points

Golf Australia's handicap ("GA Handicap") is the WHS one; GolfLink's number is the official one. The app's is an
estimate: the same sums, without the playing-conditions adjustment, the exceptional-score reductions or the caps
(soft / hard) - so a typed official handicap (settings) wins wherever one is needed.
"""
import math

# ---------------------------------------------------------------- handicaps

def half_up(x: float) -> int:
    """Round half away from zero (Python's round() is banker's: 2.5 -> 2)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def daily_handicap(index, slope, rating, par: int, allowance: float = 0.93, nine: bool = False):
    """Strokes you get today. `rating` and `par` are for the holes you play (a nine: half the 18-hole rating when the
    nine's own isn't known); a 9-hole round uses half your index. None without an index."""
    if index is None:
        return None
    index = float(index) / (2 if nine else 1)
    slope = slope or 113
    rating = float(rating) if rating is not None else par
    return half_up((index * slope / 113 + (rating - par)) * float(allowance))


def received(daily, si, nine_si: list | None = None) -> int:
    """Strokes received on a hole. An 18-hole round: one on each hole whose stroke index is at most the daily handicap,
    two once it passes 18... A nine: the hole's rank among the nine's stroke indexes (nine_si). A plus handicap gives
    strokes back from the easiest holes (the highest indexes)."""
    if daily is None or si is None:
        return 0
    holes = 9 if nine_si else 18
    rank = sorted(nine_si).index(si) + 1 if nine_si else si
    if daily < 0:
        return -1 if rank > holes + daily else 0
    return daily // holes + (1 if rank <= daily % holes else 0)


def stableford(strokes, par: int, got: int) -> int:
    """Stableford points: net par 2, net birdie 3, net bogey 1, worse (or a pick-up: strokes None) 0."""
    if strokes is None:
        return 0
    return max(0, par + got - strokes + 2)


def adjusted(strokes, par: int, got: int) -> int:
    """What a hole counts for a handicap: never more than net double bogey (a pick-up counts as that too)."""
    cap = par + 2 + got
    return cap if strokes is None else min(strokes, cap)


def differential(ags: int, rating, slope) -> float:
    return round((113 / (slope or 113)) * (ags - float(rating)), 1)


def nine_to_18(d9: float, index) -> float | None:
    """WHS (2024): a 9-hole score differential + the expected differential for the other nine (0.52 x index + 1.2)."""
    if index is None:
        return None
    return round(d9 + 0.52 * float(index) + 1.2, 1)


# How many of your most recent differentials count, and the adjustment (World Handicap System, Rule 5.2).
WHS_TABLE = {3: (1, -2.0), 4: (1, -1.0), 5: (1, 0), 6: (2, -1.0), 7: (2, 0), 8: (2, 0), 9: (3, 0), 10: (3, 0), 11: (3, 0),
             12: (4, 0), 13: (4, 0), 14: (4, 0), 15: (5, 0), 16: (5, 0), 17: (6, 0), 18: (6, 0), 19: (7, 0), 20: (8, 0)}


def handicap_index(diffs: list[tuple]) -> dict | None:
    """diffs: [(key, differential)], newest first. The index from the last 20 (fewer than 3: None), and which counted."""
    recent = [d for d in diffs if d[1] is not None][:20]
    if len(recent) < 3:
        return None
    use, adjust = WHS_TABLE[len(recent)]
    best = sorted(recent, key=lambda d: d[1])[:use]
    value = round(sum(d[1] for d in best) / use + adjust, 1)
    return {"index": min(54.0, value), "used": [d[0] for d in best], "of": len(recent), "best": use}


# ---------------------------------------------------------------- strokes gained
# Mark Broadie's PGA Tour baseline ("Every Shot Counts", 2014): average strokes to hole out by distance (yards; the
# green's in feet) and lie. Typed from general knowledge, rounded: close enough to say WHERE you lose strokes (the
# category furthest below zero), not to two decimals. Every amateur is below zero against a tour pro.
_Y = [20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 320, 340, 360, 380, 400, 420, 440, 460,
      480, 500, 520, 540, 560, 580, 600]
BASELINE = {
    "tee":      [None, None, None, None, 2.92, 2.99, 2.97, 2.99, 3.05, 3.12, 3.17, 3.25, 3.45, 3.65, 3.71, 3.79, 3.86,
                 3.92, 3.96, 3.99, 4.02, 4.08, 4.17, 4.28, 4.41, 4.54, 4.65, 4.74, 4.79, 4.82],
    "fairway":  [2.40, 2.60, 2.70, 2.75, 2.80, 2.85, 2.91, 2.98, 3.08, 3.19, 3.32, 3.45, 3.58, 3.69, 3.78, 3.84, 3.88,
                 3.95, 4.03, 4.11, 4.15, 4.20, 4.29, 4.40, 4.53, 4.66, 4.78, 4.86, 4.91, 4.94],
    "rough":    [2.59, 2.78, 2.91, 2.96, 3.02, 3.08, 3.15, 3.23, 3.31, 3.42, 3.53, 3.64, 3.74, 3.83, 3.90, 3.95, 4.02,
                 4.11, 4.21, 4.30, 4.34, 4.39, 4.48, 4.59, 4.72, 4.85, 4.97, 5.05, 5.10, 5.13],
    "sand":     [2.53, 2.82, 3.15, 3.24, 3.23, 3.21, 3.22, 3.28, 3.40, 3.55, 3.70, 3.84, 3.93, 4.00, 4.04, 4.12, 4.26,
                 4.41, 4.55, 4.69, 4.73, 4.78, 4.87, 4.98, 5.11, 5.24, 5.36, 5.44, 5.49, 5.52],
    "recovery": [None, None, None, None, 3.80, 3.78, 3.80, 3.81, 3.82, 3.87, 3.92, 3.97, 4.03, 4.10, 4.20, 4.31, 4.44,
                 4.56, 4.66, 4.75, 4.79, 4.84, 4.93, 5.04, 5.17, 5.30, 5.42, 5.50, 5.55, 5.58],
}
_FT = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 30, 40, 50, 60, 90]
PUTTS = [1.00, 1.01, 1.04, 1.13, 1.23, 1.34, 1.42, 1.50, 1.56, 1.61, 1.78, 1.87, 1.98, 2.06, 2.14, 2.21, 2.40]


def _between(xs, ys, x):
    pts = [(a, b) for a, b in zip(xs, ys) if b is not None]
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def expected(lie: str, metres: float) -> float:
    """A tour pro's strokes to hole out from `metres` away (to the middle of the green), in this lie."""
    if lie == "green":
        return _between(_FT, PUTTS, metres / 0.3048)
    return _between(_Y, BASELINE.get(lie, BASELINE["rough"]), metres / 0.9144)


def shot_category(lie: str, metres: float, par: int, first: bool) -> str:
    if lie == "green":
        return "putting"
    if first and par >= 4:
        return "off_tee"
    return "around_green" if metres <= 30 else "approach"


def hole_strokes_gained(par: int, shots: list[dict], pin, putts, first_putt_m, penalties: int, strokes) -> dict | None:
    """One hole's strokes gained by category ({off_tee, approach, around_green, putting}: None = not known), or None.
    Putting needs the putts and the first putt's length. The rest needs the shots marked from the tee until the ball
    is on the green ([{lie, lat, lon}] in order), the green's middle (pin), and every stroke accounted for:
    shots + putts + penalties = strokes."""
    if strokes is None or putts is None:
        return None
    out = dict.fromkeys(("off_tee", "approach", "around_green", "putting"))
    on_green = 0.0 if putts == 0 else expected("green", float(first_putt_m)) if first_putt_m is not None else None
    if putts > 0 and on_green is not None:
        out["putting"] = round(on_green - putts, 3)
    if shots and pin is not None and on_green is not None and len(shots) + putts + (penalties or 0) == strokes:
        for k in ("off_tee", "approach", "around_green"):
            out[k] = 0.0
        states = [(s["lie"], metres_between((s["lat"], s["lon"]), pin)) for s in shots]
        for i, (lie, dist) in enumerate(states):
            after = expected(*states[i + 1]) if i + 1 < len(states) else on_green
            out[shot_category(lie, dist, par, i == 0)] += expected(lie, dist) - after - 1
        out["off_tee"] -= penalties or 0       # (penalties charged to the tee shot: the usual simplification)
        for k in ("off_tee", "approach", "around_green"):
            out[k] = round(out[k], 3)
    return out if any(v is not None for v in out.values()) else None


# ---------------------------------------------------------------- "plays like a ..."
# Rough averages by handicap from published amateur stats (Shot Scope, Arccos - typed from general knowledge, like the
# strokes-gained table): fairways hit %, greens in regulation %, putts a round, scrambling %, three-putts and
# penalties a round. Used only to say which part of your game is furthest behind the rest.
BENCH_HCP = [0, 5, 10, 15, 20, 25, 30]
BENCH = {
    "fairways": [60, 54, 48, 43, 38, 34, 30],
    "gir": [56, 45, 35, 26, 19, 12, 8],
    "putts": [30.0, 31.0, 32.0, 33.0, 34.0, 35.0, 36.0],
    "scrambling": [50, 38, 29, 22, 16, 12, 9],
    "three_putts": [0.9, 1.2, 1.6, 2.0, 2.5, 3.0, 3.5],
    "penalties": [0.6, 0.9, 1.3, 1.7, 2.2, 2.7, 3.2],
}


def plays_like(stat: str, value) -> float | None:
    """The handicap whose average matches your number (0 - 36: past the table it's extended in a straight line)."""
    if value is None or stat not in BENCH:
        return None
    ys, xs = BENCH[stat], BENCH_HCP
    rising = ys[-1] > ys[0]                  # putts, three-putts, penalties go up with the handicap
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if (y0 <= value <= y1) if rising else (y1 <= value <= y0):
            return round(x0 + (x1 - x0) * (value - y0) / (y1 - y0), 1)
    (x0, y0), (x1, y1) = ((xs[0], ys[0]), (xs[1], ys[1])) if ((value < ys[0]) if rising else (value > ys[0])) \
        else ((xs[-2], ys[-2]), (xs[-1], ys[-1]))
    return round(max(-5.0, min(40.0, x0 + (x1 - x0) * (value - y0) / (y1 - y0))), 1)


def bench_at(stat: str, hcp: float) -> float:
    return round(_between(BENCH_HCP, BENCH[stat], hcp), 1)


# ---------------------------------------------------------------- the map

def metres_between(a, b) -> float:
    """Haversine distance between two (lat, lon) points."""
    r = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def centre(points: list) -> tuple | None:
    """The middle of a shape (the average of its corners: fine for a green)."""
    if not points:
        return None
    pts = points[:-1] if len(points) > 2 and points[0] == points[-1] else points
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
