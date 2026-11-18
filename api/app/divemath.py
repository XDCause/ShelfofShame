"""Dive maths (Scuba diving): pure functions, no database. FOR LEARNING AND CHECKING ONLY - a dive computer and your
training are the rule, never this file.

Decompression model: Buhlmann ZHL-16C (16 compartments, nitrogen and helium half-times and a / b values as published in
Buhlmann's "Tauchmedizin") with gradient factors (Erik Baker): the tolerated pressure in each tissue is cut back to a
fraction GF of the way from the ambient pressure to the M-value. GF low applies at the first stop (the deepest ceiling),
GF high at the surface, in a straight line between.

    Tissues, new_tissues()          the 16 compartments' nitrogen / helium pressures (bar)
    schreiner(...)                  loading over a change of depth (the Schreiner equation; constant depth is a ramp of 0)
    ceiling(...), surface_gf(...)   the depth you can't go above (at a GF); how stressed the tissues are at the surface
    ndl(depth, o2, gf_high)         no-decompression limit in minutes, counted from leaving the surface (descent included)
    plan(...)                       a planned dive: stops (3 m steps, last stop 3 m), time to surface, gas, oxygen, warnings
    tissues_after(samples, ...)     a recorded profile's end state, and its leading compartment over time
    ppo2, mod, ead, best_mix        the nitrox sums (1 bar at the surface, 10 m of water = 1 bar)
    exposure(...)                   CNS % (NOAA table) and OTU of a profile
    rock_bottom_l / gas_plan        the gas assumptions (see their docstrings)
    ascent_warnings, safety_stop    checks over a recorded profile

Assumptions (all of them): 10 m of water = 1 bar, surface pressure 1.013 bar, water vapour 0.0627 bar, air is 21 % oxygen
and 79 % nitrogen, descent 18 m/min, ascent 9 m/min, one breathing gas all dive. Times are minutes, depths metres.
The tables are published (Buhlmann; NOAA oxygen exposure limits); they're typed here from the published numbers.
"""
import math
from dataclasses import dataclass, field

SURFACE = 1.013                 # bar
WATER_VAPOUR = 0.0627           # bar
AIR_N2 = 0.79
DESCENT = 18.0                  # m/min
ASCENT = 9.0                    # m/min
STEP = 3.0                      # stop spacing, and the last stop's depth (m)
NDL_CAP = 300                   # minutes: a shallower dive than that is "300+"
MAX_ASCENT_RATE = 10.0          # m/min over the 30 s window below
ASCENT_WINDOW = 30.0            # seconds

# half-time (min), a, b for nitrogen then helium; 16 compartments (1, 1b, 2 ... 15)
N2_HALF = [5.0, 8.0, 12.5, 18.5, 27.0, 38.3, 54.3, 77.0, 109.0, 146.0, 187.0, 239.0, 305.0, 390.0, 498.0, 635.0]
N2_A = [1.1696, 1.0, 0.8618, 0.7562, 0.62, 0.5043, 0.441, 0.4, 0.375, 0.35, 0.3295, 0.3065, 0.2835, 0.261, 0.248, 0.2327]
N2_B = [0.5578, 0.6514, 0.7222, 0.7825, 0.8126, 0.8434, 0.8693, 0.891, 0.9092, 0.9222, 0.9319, 0.9403, 0.9477, 0.9544, 0.9602, 0.9653]
HE_HALF = [1.88, 3.02, 4.72, 6.99, 10.21, 14.48, 20.53, 29.11, 41.2, 55.19, 70.69, 90.34, 115.29, 147.42, 188.24, 240.03]
HE_A = [1.6189, 1.383, 1.1919, 1.0458, 0.922, 0.8205, 0.7305, 0.6502, 0.595, 0.5545, 0.5333, 0.5189, 0.5181, 0.5176, 0.5172, 0.5119]
HE_B = [0.477, 0.5747, 0.6527, 0.7223, 0.7582, 0.7957, 0.8279, 0.8553, 0.8757, 0.8903, 0.8997, 0.9073, 0.9122, 0.9171, 0.9217, 0.9267]
N = 16
K_N2 = [math.log(2) / h for h in N2_HALF]
K_HE = [math.log(2) / h for h in HE_HALF]

# NOAA single-exposure limits: ppO2 (bar) -> minutes for 100 % CNS
CNS_TABLE = [(0.5, 800.0), (0.6, 720.0), (0.7, 570.0), (0.8, 450.0), (0.9, 360.0), (1.0, 300.0), (1.1, 270.0),
             (1.2, 240.0), (1.3, 210.0), (1.4, 180.0), (1.5, 120.0), (1.6, 45.0)]


@dataclass
class Tissues:
    """Inert-gas pressure (bar) in each of the 16 compartments."""
    n2: list = field(default_factory=list)
    he: list = field(default_factory=list)

    def copy(self) -> "Tissues":
        return Tissues(list(self.n2), list(self.he))


def new_tissues() -> Tissues:
    """Saturated on air at the surface (what you start a day's diving with)."""
    return Tissues([(SURFACE - WATER_VAPOUR) * AIR_N2] * N, [0.0] * N)


def amb(depth: float) -> float:
    """Ambient pressure (bar) at a depth, for the tissue sums."""
    return SURFACE + max(depth, 0.0) / 10.0


def gas(o2: float, he: float = 0.0) -> tuple[float, float, float]:
    """(fraction O2, He, N2) from percentages: gas(32) -> (0.32, 0.0, 0.68)."""
    fo2, fhe = o2 / 100.0, he / 100.0
    return fo2, fhe, max(0.0, 1.0 - fo2 - fhe)


def schreiner(t: Tissues, d0: float, d1: float, minutes: float, o2: float = 21.0, he: float = 0.0) -> Tissues:
    """Load the tissues (in place) over `minutes` while going from depth d0 to d1 in a straight line (equal depths: a
    stay). The Schreiner equation: P = Pi0 + R (t - 1/k) - (Pi0 - P0 - R/k) e^(-k t), where Pi0 is the inspired inert
    gas pressure at the start, R how fast it changes (bar/min), k = ln 2 / half-time."""
    if minutes <= 0:
        return t
    _fo2, fhe, fn2 = gas(o2, he)
    p0, p1 = amb(d0), amb(d1)
    pi_n2, r_n2 = (p0 - WATER_VAPOUR) * fn2, (p1 - p0) / minutes * fn2
    for i in range(N):
        k = K_N2[i]
        t.n2[i] = pi_n2 + r_n2 * (minutes - 1 / k) - (pi_n2 - t.n2[i] - r_n2 / k) * math.exp(-k * minutes)
    if fhe or any(t.he):
        pi_he, r_he = (p0 - WATER_VAPOUR) * fhe, (p1 - p0) / minutes * fhe
        for i in range(N):
            k = K_HE[i]
            t.he[i] = pi_he + r_he * (minutes - 1 / k) - (pi_he - t.he[i] - r_he / k) * math.exp(-k * minutes)
    return t


def _ab(t: Tissues, i: int) -> tuple[float, float]:
    pn, ph = t.n2[i], t.he[i]
    total = pn + ph
    if ph <= 0 or total <= 0:
        return N2_A[i], N2_B[i]
    return (N2_A[i] * pn + HE_A[i] * ph) / total, (N2_B[i] * pn + HE_B[i] * ph) / total


def ceiling(t: Tissues, gf: float) -> float:
    """The depth (m) you must stay below at gradient factor `gf` (a fraction, 0.85): zero or negative means the surface
    is fine. P_tolerated = (P_tissue - a GF) / (GF / b - GF + 1)."""
    worst = 0.0
    for i in range(N):
        a, b = _ab(t, i)
        tol = (t.n2[i] + t.he[i] - a * gf) / (gf / b - gf + 1.0)
        worst = max(worst, tol) if i else tol
    return (worst - SURFACE) * 10.0


def gf_at(t: Tissues, depth: float) -> float:
    """The most stressed compartment's gradient factor (percent, can pass 100) at a depth: 0 = nothing to worry about
    (tissues below ambient pressure), 100 = right at the M-value. At depth 0 this is the "surface GF"; at the
    current depth it's GF99."""
    p = amb(depth)
    worst = 0.0
    for i in range(N):
        a, b = _ab(t, i)
        pt = t.n2[i] + t.he[i]
        m = p / b + a
        worst = max(worst, (pt - p) / (m - p) * 100.0)
    return worst


def surface_gf(t: Tissues) -> float:
    return gf_at(t, 0.0)


def offgas(t: Tissues, minutes: float) -> Tissues:
    """Time at the surface breathing air (a surface interval), in place."""
    return schreiner(t, 0.0, 0.0, minutes, 21.0, 0.0)


# ---------------------------------------------------------------- no-decompression limit

def ndl(depth: float, o2: float = 21.0, gf_high: float = 100.0, tissues: Tissues | None = None,
        descent: float = DESCENT) -> int:
    """Minutes from leaving the surface (the descent counts, as on dive tables) until a direct ascent would break the
    surface gradient factor `gf_high` (percent). 0 when even the descent is too much; NDL_CAP when it's longer than that.
    Pass tissues for a repetitive dive (they are left unchanged)."""
    gf = gf_high / 100.0
    t = (tissues or new_tissues()).copy()
    td = depth / descent
    schreiner(t, 0.0, depth, td, o2)
    if ceiling(t, gf) > 0:
        return 0
    step, elapsed = 0.25, td
    while elapsed < NDL_CAP:
        schreiner(t, depth, depth, step, o2)
        if ceiling(t, gf) > 0:
            return int(elapsed)
        elapsed += step
    return NDL_CAP


# ---------------------------------------------------------------- stops

def stops(t: Tissues, depth: float, o2: float, gf_low: float, gf_high: float, rate: float = ASCENT, he: float = 0.0):
    """Ascend from `depth` (tissues t, which are advanced in place to the surface) -> ([{depth, minutes}], minutes spent
    ascending between stops). Stops are every 3 m, the last at 3 m; each lasts whole minutes until the next one up is
    allowed at that depth's gradient factor (GF low at the first stop, in a line up to GF high at the surface)."""
    lo, hi = gf_low / 100.0, gf_high / 100.0
    result, ascending = [], 0.0
    if ceiling(t, hi) <= 0:                       # a direct ascent is fine
        schreiner(t, depth, 0.0, depth / rate, o2, he)
        return result, depth / rate
    first = math.ceil(ceiling(t, lo) / STEP - 1e-9) * STEP
    first = min(max(first, STEP), math.ceil(depth / STEP) * STEP)
    here = depth
    cur = first

    def gf_for(d):
        return hi - (hi - lo) * d / first if first else hi

    if here > cur:
        schreiner(t, here, cur, (here - cur) / rate, o2, he)
        ascending += (here - cur) / rate
        here = cur
    while cur > 0:
        nxt = cur - STEP if cur > STEP else 0.0
        minutes = 0
        while ceiling(t, gf_for(nxt)) > nxt:
            schreiner(t, cur, cur, 1.0, o2, he)
            minutes += 1
            if minutes > 999:
                break
        if minutes:
            result.append({"depth": int(cur), "minutes": minutes})
        schreiner(t, cur, nxt, (cur - nxt) / rate, o2, he)
        ascending += (cur - nxt) / rate
        cur = nxt
    return result, ascending


# ---------------------------------------------------------------- nitrox

def ppo2(depth: float, o2: float) -> float:
    return o2 / 100.0 * (depth / 10.0 + 1.0)


def mod(o2: float, limit: float = 1.4) -> float:
    """Maximum operating depth (m) for a mix at a ppO2 limit: EAN32 at 1.4 -> 33.75 m."""
    return (limit / (o2 / 100.0) - 1.0) * 10.0


def ead(depth: float, o2: float) -> float:
    """Equivalent air depth (m): the depth on air with the same nitrogen pressure. EAN32 at 30 m -> 24.4 m."""
    return (1.0 - o2 / 100.0) / AIR_N2 * (depth + 10.0) - 10.0


def best_mix(depth: float, limit: float = 1.4) -> int | None:
    """The richest whole-percent oxygen for a depth at a ppO2 limit (None if even air is too much there)."""
    pct = math.floor(limit / (depth / 10.0 + 1.0) * 100.0 + 1e-9)
    if pct < 21:
        return None
    return min(pct, 100)


def _cns_limit(p: float) -> float:
    """Minutes for 100 % CNS at this ppO2 (NOAA, straight lines between the table's rows)."""
    if p >= CNS_TABLE[-1][0]:
        return CNS_TABLE[-1][1]
    for (p0, m0), (p1, m1) in zip(CNS_TABLE, CNS_TABLE[1:]):
        if p <= p1:
            return m0 + (m1 - m0) * (p - p0) / (p1 - p0)
    return CNS_TABLE[-1][1]


def cns_rate(p: float) -> float:
    """CNS % per minute at a ppO2 (nothing below 0.5 bar)."""
    return 0.0 if p < 0.5 else 100.0 / _cns_limit(p)


def otu_rate(p: float) -> float:
    """Oxygen toxicity units per minute at a ppO2 (pulmonary; nothing at or below 0.5 bar)."""
    return 0.0 if p <= 0.5 else ((p - 0.5) / 0.5) ** (5.0 / 6.0)


def exposure(segments: list[tuple[float, float, float]], o2: float) -> tuple[float, float]:
    """(CNS %, OTU) over segments [(minutes, depth at start, depth at end)], the ppO2 taken at each one's middle (cut a
    steep segment into pieces and it's more exact)."""
    cns = otu = 0.0
    for minutes, d0, d1 in segments:
        p = ppo2((d0 + d1) / 2.0, o2)
        cns += cns_rate(p) * minutes
        otu += otu_rate(p) * minutes
    return cns, otu


# ---------------------------------------------------------------- gas

def segment_litres(segments, sac: float) -> float:
    """Litres breathed at `sac` (L/min at the surface) over [(minutes, d0, d1)]."""
    return sum(sac * (1.0 + (d0 + d1) / 20.0) * m for m, d0, d1 in segments)


def rock_bottom_l(depth: float, sac: float, rate: float = ASCENT) -> float:
    """Gas (litres) to keep in reserve at the deepest point: TWO divers, both stressed (SAC x 2 each), solve a problem
    for 1 minute at depth, then swim up together to the surface at 9 m/min (no stop counted). Your own air isn't enough
    when your buddy's out of gas: this is the gas for both of you."""
    stressed = sac * 2.0 * 2.0                     # two divers' SAC, each doubled
    return segment_litres([(1.0, depth, depth), (depth / rate, depth, 0.0)], stressed)


def gas_plan(total_l: float, depth: float, sac: float, tank_l: float, start_bar: float) -> dict:
    """Pressures for a tank: used, left, rock bottom (see rock_bottom_l) and the turn pressure - the rule of thirds on
    the gas above rock bottom (turn when a third of it is used)."""
    used = math.ceil(total_l / tank_l)
    rock = math.ceil(rock_bottom_l(depth, sac) / tank_l)
    usable = max(0.0, start_bar - rock)
    return {"gas_l": round(total_l), "gas_bar": used, "end_bar": int(start_bar - used), "rock_bottom_bar": rock,
            "turn_bar": int(math.ceil(start_bar - usable / 3.0))}


# ---------------------------------------------------------------- a planned dive

def plan(depth: float, minutes: float, o2: float = 21.0, gf_low: float = 40.0, gf_high: float = 85.0, sac: float = 20.0,
         tank_l: float = 12.0, start_bar: float = 200.0, tissues: Tissues | None = None, ppo2_max: float = 1.4,
         he: float = 0.0) -> dict:
    """A square dive: down at 18 m/min, level until `minutes` have passed since leaving the surface (the descent counts),
    then up at 9 m/min with any stops. -> {ndl, stops [{depth, minutes}], tts, runtime, ppo2, mod, cns, otu, gas_l,
    gas_bar, end_bar, turn_bar, rock_bottom_bar, warnings}. tts = minutes from leaving the bottom to the surface;
    runtime = minutes + tts; ndl is for THIS start (fresh tissues, or the ones given)."""
    td = depth / DESCENT
    minutes = max(float(minutes), td)
    t = (tissues or new_tissues()).copy()
    schreiner(t, 0.0, depth, td, o2, he)
    schreiner(t, depth, depth, minutes - td, o2, he)
    found, ascending = stops(t, depth, o2, gf_low, gf_high, he=he)
    # the shape of it, for gas and oxygen: [(minutes, d0, d1)]
    segs = [(td, 0.0, depth), (minutes - td, depth, depth)]
    here = depth
    for s in found:
        d = float(s["depth"])
        if here > d:
            segs.append(((here - d) / ASCENT, here, d))
        segs.append((float(s["minutes"]), d, d))
        here = d
    if here > 0:
        segs.append((here / ASCENT, here, 0.0))
    pieces = []
    for m, d0, d1 in segs:                          # (steep pieces cut up for the oxygen sum)
        n = max(1, int(abs(d1 - d0) // 3))
        pieces += [(m / n, d0 + (d1 - d0) * i / n, d0 + (d1 - d0) * (i + 1) / n) for i in range(n)]
    cns, otu = exposure(pieces, o2)
    stop_min = sum(s["minutes"] for s in found)
    tts = ascending + stop_min
    out = {"ndl": ndl(depth, o2, gf_high, tissues), "stops": found, "tts": round(tts, 1), "runtime": round(minutes + tts, 1),
           "ppo2": round(ppo2(depth, o2), 2), "mod": round(mod(o2, ppo2_max), 1), "cns": round(cns, 1), "otu": round(otu)}
    out.update(gas_plan(segment_litres(segs, sac), depth, sac, tank_l, start_bar))
    warn = []
    if ppo2(depth, o2) > ppo2_max + 1e-9:
        warn.append(f"The ppO2 at {depth:g} m is {ppo2(depth, o2):.2f} bar, over your {ppo2_max:g} limit: this mix is good to {mod(o2, ppo2_max):.1f} m.")
    if depth > 40:
        warn.append("Deeper than 40 m is beyond recreational limits and needs technical training.")
    if found:
        warn.append("This dive needs decompression stops: more than a recreational (no-stop) dive. Plan within your no-stop limit unless you are trained for it.")
    if out["end_bar"] < out["rock_bottom_bar"]:
        warn.append(f"You'd reach the surface with {max(out['end_bar'], 0)} bar, under the rock bottom of {out['rock_bottom_bar']} bar.")
    if out["end_bar"] < 0:
        warn.append("There isn't enough gas in this tank for the plan.")
    if cns >= 80:
        warn.append(f"CNS {cns:.0f} %: close to the oxygen limit.")
    out["warnings"] = warn
    return out


# ---------------------------------------------------------------- a recorded profile

def clean_samples(samples) -> list[tuple[float, float]]:
    """[[seconds, depth, temp], ...] -> [(seconds, depth)] in time order, starting at the surface."""
    pts = sorted((float(s[0]), max(0.0, float(s[1]))) for s in samples if s and len(s) >= 2 and s[0] is not None and s[1] is not None)
    if pts and pts[0][0] > 0:
        pts.insert(0, (0.0, 0.0))
    return pts


def tissues_after(samples, o2: float = 21.0, tissues: Tissues | None = None, series_max: int = 200) -> tuple[Tissues, list]:
    """Walk a recorded profile -> (the tissues at its end, [[seconds, leading %]]). The leading % is the most stressed
    compartment's percent of its M-value at that moment (gradient-factor scale, 0 when everything is below ambient) -
    GF99. The series is thinned to about `series_max` points."""
    pts = clean_samples(samples)
    t = (tissues or new_tissues()).copy()
    series = []
    step = max(1, math.ceil(len(pts) / max(series_max - 5, 1)))
    for i, (s, d) in enumerate(pts):
        if i:
            s0, d0 = pts[i - 1]
            schreiner(t, d0, d, (s - s0) / 60.0, o2)
        if i % step == 0 or i == len(pts) - 1:
            series.append([int(s), round(max(0.0, gf_at(t, d)), 1)])
    return t, series


def profile_exposure(samples, o2: float = 21.0) -> tuple[float, float, float]:
    """(CNS %, OTU, highest ppO2) of a recorded profile."""
    pts = clean_samples(samples)
    segs = [((s - s0) / 60.0, d0, d) for (s0, d0), (s, d) in zip(pts, pts[1:]) if s > s0]
    cns, otu = exposure(segs, o2)
    peak = ppo2(max((d for _s, d in pts), default=0.0), o2)
    return cns, otu, peak


def ascent_warnings(samples, limit: float = MAX_ASCENT_RATE, window: float = ASCENT_WINDOW) -> list[dict]:
    """Stretches where you came up faster than `limit` m/min, measured over at least `window` seconds (a single jumpy
    sample isn't one): [{from_s, to_s, rate}] - overlapping windows are joined and the worst rate kept."""
    pts = clean_samples(samples)
    found, j = [], 0
    for i, (s0, d0) in enumerate(pts):
        j = max(j, i + 1)
        while j < len(pts) and pts[j][0] - s0 < window:
            j += 1
        if j >= len(pts):
            break
        s1, d1 = pts[j]
        rate = (d0 - d1) / ((s1 - s0) / 60.0)
        if rate > limit:
            if found and s0 <= found[-1]["to_s"]:
                found[-1]["to_s"] = int(s1)
                found[-1]["rate"] = max(found[-1]["rate"], round(rate, 1))
            else:
                found.append({"from_s": int(s0), "to_s": int(s1), "rate": round(rate, 1)})
    return found


def safety_stop(samples, low: float = 3.0, high: float = 6.0, need: float = 180.0) -> dict:
    """Did you stop between 3 and 6 m on the way up? Counts the seconds spent at 3-6 m (half a metre either side for a
    computer's rounding) after the last time you were deeper than 6 m; found when that's at least 3 minutes."""
    pts = clean_samples(samples)
    last_deep = max((i for i, (_s, d) in enumerate(pts) if d > high + 0.5), default=None)
    if last_deep is None:
        return {"found": False, "seconds": 0}
    seconds = 0.0
    for (s0, d0), (s1, d1) in zip(pts[last_deep:], pts[last_deep + 1:]):
        if low - 0.5 <= (d0 + d1) / 2.0 <= high + 0.5 and d1 > 0.5:
            seconds += s1 - s0
    return {"found": seconds >= need, "seconds": int(seconds)}


def downsample(samples, most: int = 400) -> list:
    """At most about `most` samples, keeping the first, the last and the deepest."""
    if len(samples) <= most:
        return [list(s) for s in samples]
    step = math.ceil(len(samples) / (most - 2))
    keep = set(range(0, len(samples), step)) | {len(samples) - 1, max(range(len(samples)), key=lambda i: samples[i][1] or 0)}
    return [list(samples[i]) for i in sorted(keep)]
