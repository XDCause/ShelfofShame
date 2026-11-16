"""Precision shooting: a ballistic solver, the air it flies through, and how your ammo's speed follows the temperature.

    GET /shooting/ballistics?rifle_id=&ammo_id=...        drop, wind drift, time of flight and speed per distance, worked
                                                          out from the ammo's BC (G1 or G7) and muzzle velocity, the rifle's
                                                          sight height and zero, and the air (temperature, pressure, humidity)
    GET /shooting/ammo/{id}/temp-sensitivity?rifle_id=    fps per degree, fitted from your chronograph sessions

The maths is pure (no database): standard drag tables, a point-mass trajectory, the atmosphere, a straight-line fit.
Everything is metric inside; the answers also come in MOA / MIL and cm.

Sources (public domain / textbook):
  - G1 and G7 drag coefficient against Mach: the standard tables from the Ballistic Research Laboratory's / Ingalls'
    work, as printed in the GNU Exterior Ballistics Computer and the Wikipedia "Ballistic coefficient" lists.
  - Ballistic coefficient: deceleration = rho * pi * v^2 * Cd(Mach) / (8 * 703.0696 * BC); BC in lb/in^2, 703.0696 kg/m^2 per lb/in^2.
  - Atmosphere: ICAO standard 15 C, 1013.25 hPa, density 1.225 kg/m^3; vapour pressure by the Tetens formula;
    density altitude from the ICAO density-height relation.
  - Wind drift: the lag-time rule, crosswind x (time of flight - distance / muzzle velocity).
"""
import math
from bisect import bisect_right

from fastapi import APIRouter, HTTPException, Query

from .db import db, found

router = APIRouter(prefix="/api", tags=["shooting"])

G = 9.80665
RHO0 = 1.225                  # kg/m^3, ICAO standard air at sea level
STD_TEMP_C, STD_PRESSURE_HPA = 15.0, 1013.25
BC_TO_SI = 703.0696           # 1 lb/in^2 in kg/m^2
GRAIN_KG = 0.00006479891
MRAD_TO_MOA = 180 * 60 / math.pi / 1000
DEFAULT_SIGHT_MM = 45.0       # a typical scope on rings, if the rifle hasn't got one entered

# Drag coefficient against Mach number: (mach, Cd).
G1 = [(0.00, 0.2629), (0.05, 0.2558), (0.10, 0.2487), (0.15, 0.2413), (0.20, 0.2344), (0.25, 0.2278), (0.30, 0.2214),
      (0.35, 0.2155), (0.40, 0.2104), (0.45, 0.2061), (0.50, 0.2032), (0.55, 0.2020), (0.60, 0.2034), (0.70, 0.2165),
      (0.725, 0.2230), (0.75, 0.2313), (0.775, 0.2417), (0.80, 0.2546), (0.825, 0.2706), (0.85, 0.2901), (0.875, 0.3136),
      (0.90, 0.3415), (0.925, 0.3734), (0.95, 0.4084), (0.975, 0.4448), (1.00, 0.4805), (1.025, 0.5136), (1.05, 0.5427),
      (1.075, 0.5677), (1.10, 0.5883), (1.125, 0.6053), (1.15, 0.6191), (1.20, 0.6393), (1.25, 0.6518), (1.30, 0.6589),
      (1.35, 0.6621), (1.40, 0.6625), (1.45, 0.6607), (1.50, 0.6573), (1.55, 0.6528), (1.60, 0.6474), (1.65, 0.6413),
      (1.70, 0.6347), (1.75, 0.6280), (1.80, 0.6210), (1.85, 0.6141), (1.90, 0.6072), (1.95, 0.6003), (2.00, 0.5934),
      (2.05, 0.5867), (2.10, 0.5804), (2.15, 0.5743), (2.20, 0.5685), (2.25, 0.5630), (2.30, 0.5577), (2.35, 0.5527),
      (2.40, 0.5481), (2.45, 0.5438), (2.50, 0.5397), (2.60, 0.5325), (2.70, 0.5264), (2.80, 0.5211), (2.90, 0.5168),
      (3.00, 0.5133), (3.10, 0.5105), (3.20, 0.5084), (3.30, 0.5067), (3.40, 0.5054), (3.50, 0.5040), (3.60, 0.5030),
      (3.70, 0.5022), (3.80, 0.5016), (3.90, 0.5010), (4.00, 0.5006), (4.20, 0.4998), (4.40, 0.4995), (4.60, 0.4992),
      (4.80, 0.4990), (5.00, 0.4988)]
G7 = [(0.00, 0.1198), (0.05, 0.1197), (0.10, 0.1196), (0.15, 0.1194), (0.20, 0.1193), (0.25, 0.1194), (0.30, 0.1194),
      (0.35, 0.1194), (0.40, 0.1193), (0.45, 0.1193), (0.50, 0.1194), (0.55, 0.1193), (0.60, 0.1194), (0.65, 0.1197),
      (0.70, 0.1202), (0.725, 0.1207), (0.75, 0.1215), (0.775, 0.1226), (0.80, 0.1242), (0.825, 0.1266), (0.85, 0.1306),
      (0.875, 0.1368), (0.90, 0.1464), (0.925, 0.1660), (0.95, 0.2054), (0.975, 0.2993), (1.00, 0.3803), (1.025, 0.4015),
      (1.05, 0.4043), (1.075, 0.4034), (1.10, 0.4014), (1.125, 0.3987), (1.15, 0.3955), (1.20, 0.3884), (1.25, 0.3810),
      (1.30, 0.3732), (1.35, 0.3657), (1.40, 0.3580), (1.50, 0.3440), (1.55, 0.3376), (1.60, 0.3315), (1.65, 0.3260),
      (1.70, 0.3209), (1.75, 0.3160), (1.80, 0.3117), (1.85, 0.3078), (1.90, 0.3042), (1.95, 0.3010), (2.00, 0.2980),
      (2.05, 0.2951), (2.10, 0.2922), (2.15, 0.2892), (2.20, 0.2864), (2.25, 0.2835), (2.30, 0.2807), (2.35, 0.2779),
      (2.40, 0.2752), (2.45, 0.2725), (2.50, 0.2697), (2.55, 0.2670), (2.60, 0.2643), (2.65, 0.2615), (2.70, 0.2588),
      (2.75, 0.2561), (2.80, 0.2533), (2.85, 0.2506), (2.90, 0.2479), (2.95, 0.2451), (3.00, 0.2424), (3.10, 0.2368),
      (3.20, 0.2313), (3.30, 0.2258), (3.40, 0.2205), (3.50, 0.2154), (3.60, 0.2106), (3.70, 0.2060), (3.80, 0.2017),
      (3.90, 0.1975), (4.00, 0.1935), (4.20, 0.1861), (4.40, 0.1793), (4.60, 0.1730), (4.80, 0.1672), (5.00, 0.1618)]
TABLES = {"G1": G1, "G7": G7}
_MACH = {name: [m for m, _ in table] for name, table in TABLES.items()}


def drag_cd(model: str, mach: float) -> float:
    """The standard drag coefficient at a Mach number (straight line between table rows; flat beyond the ends)."""
    table, machs = TABLES[model], _MACH[model]
    if mach <= machs[0]:
        return table[0][1]
    if mach >= machs[-1]:
        return table[-1][1]
    i = bisect_right(machs, mach)
    (m0, c0), (m1, c1) = table[i - 1], table[i]
    return c0 + (c1 - c0) * (mach - m0) / (m1 - m0)


# ---------------------------------------------------------------------------------------------
# The air
# ---------------------------------------------------------------------------------------------
def vapour_pressure_hpa(temp_c: float, humidity_pct: float) -> float:
    """Water vapour's share of the pressure (Tetens): saturation pressure x relative humidity."""
    return 6.1078 * 10 ** (7.5 * temp_c / (temp_c + 237.3)) * humidity_pct / 100


def air_density(temp_c: float, pressure_hpa: float, humidity_pct: float = 0) -> float:
    """kg/m^3 from temperature, STATION pressure (not the weather map's sea-level figure) and humidity."""
    kelvin = temp_c + 273.15
    wet = min(vapour_pressure_hpa(temp_c, humidity_pct), pressure_hpa)
    return (pressure_hpa - wet) * 100 / (287.058 * kelvin) + wet * 100 / (461.495 * kelvin)


def density_altitude_m(rho: float) -> float:
    """The height in the standard atmosphere that has this air density (ICAO)."""
    return 44330.77 * (1 - (rho / RHO0) ** 0.234969)


def speed_of_sound(temp_c: float) -> float:
    return 331.3 * math.sqrt(1 + temp_c / 273.15)


def atmosphere(temp_c: float | None = None, pressure_hpa: float | None = None, humidity_pct: float | None = None) -> dict:
    """The air as numbers; anything not given is the standard day (15 C, 1013.25 hPa, dry)."""
    t = STD_TEMP_C if temp_c is None else temp_c
    p = STD_PRESSURE_HPA if pressure_hpa is None else pressure_hpa
    h = 0.0 if humidity_pct is None else humidity_pct
    rho = air_density(t, p, h)
    return {"temp_c": t, "pressure_hpa": p, "humidity_pct": h, "density": round(rho, 4), "rho": rho,
            "density_altitude_m": round(density_altitude_m(rho)), "sound_ms": round(speed_of_sound(t), 1),
            "standard": temp_c is None and pressure_hpa is None and humidity_pct is None}


# ---------------------------------------------------------------------------------------------
# The flight
# ---------------------------------------------------------------------------------------------
def _accel(vx: float, vy: float, k: float, model: str, rho: float, sound: float) -> tuple[float, float]:
    v = math.hypot(vx, vy)
    decel = rho * math.pi * v * v * drag_cd(model, v / sound) / (8 * BC_TO_SI * k)     # k = the BC
    return -decel * vx / v, -decel * vy / v - G


def fly(mv: float, bc: float, model: str, angle: float, atm: dict, distances: list[float], height_m: float, dt: float = 0.002) -> list[dict]:
    """A point mass leaving the bore at `angle` (radians above the sight line), `height_m` above the bore's line of sight
    (negative: the bore is below the scope). One row per distance: height above the sight line, time, speed. Midpoint /
    RK4 steps of dt seconds; stops early if the bullet stops moving forward."""
    rho, sound = atm["rho"], atm["sound_ms"]
    x, y, vx, vy, t = 0.0, height_m, mv * math.cos(angle), mv * math.sin(angle), 0.0
    out, todo = [], sorted(distances)
    while todo and vx > 5 and t < 30:
        a1x, a1y = _accel(vx, vy, bc, model, rho, sound)
        a2x, a2y = _accel(vx + a1x * dt / 2, vy + a1y * dt / 2, bc, model, rho, sound)
        a3x, a3y = _accel(vx + a2x * dt / 2, vy + a2y * dt / 2, bc, model, rho, sound)
        a4x, a4y = _accel(vx + a3x * dt, vy + a3y * dt, bc, model, rho, sound)
        nvx = vx + (a1x + 2 * a2x + 2 * a3x + a4x) * dt / 6
        nvy = vy + (a1y + 2 * a2y + 2 * a3y + a4y) * dt / 6
        nx, ny = x + (vx + nvx) / 2 * dt, y + (vy + nvy) / 2 * dt
        while todo and todo[0] <= nx:
            f = (todo[0] - x) / (nx - x) if nx > x else 0
            out.append({"x": todo[0], "y": y + (ny - y) * f, "t": t + dt * f,
                        "v": math.hypot(vx + (nvx - vx) * f, vy + (nvy - vy) * f)})
            todo.pop(0)
        x, y, vx, vy, t = nx, ny, nvx, nvy, t + dt
    return out


def zero_angle(mv: float, bc: float, model: str, atm: dict, zero_m: float, sight_m: float) -> float:
    """The launch angle that brings the bullet back to the line of sight at zero_m (bisection)."""
    lo, hi = -0.02, 0.25
    for _ in range(45):
        mid = (lo + hi) / 2
        hit = fly(mv, bc, model, mid, atm, [zero_m], -sight_m)
        if not hit or hit[0]["y"] > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def trajectory(mv: float, bc: float, model: str, zero_m: float, sight_mm: float, distances: list[float], shot_air: dict,
               zero_air: dict | None = None, wind_ms: float = 0, bullet_kg: float | None = None, mv_zero: float | None = None) -> list[dict]:
    """The table: for each distance, drop against the sight line (cm; negative = below), the elevation to dial to put it
    back (mrad, MOA), wind drift for `wind_ms` of crosswind (cm; mrad), time of flight and speed. The scope is zeroed in
    `zero_air` (default: the same air as the shot) with the muzzle velocity `mv_zero` (default mv)."""
    zero_air = zero_air or shot_air
    sight_m = sight_mm / 1000
    angle = zero_angle(mv_zero or mv, bc, model, zero_air, zero_m, sight_m)
    rows = []
    for r in fly(mv, bc, model, angle, shot_air, [float(d) for d in distances], -sight_m):
        x = r["x"]
        lag = max(r["t"] - x / mv, 0)
        drift = wind_ms * lag
        up_mrad = -math.atan(r["y"] / x) * 1000 if x else 0
        rows.append({"m": round(x), "drop_cm": round(r["y"] * 100, 1), "elev_mrad": round(up_mrad, 2),
                     "elev_moa": round(up_mrad * MRAD_TO_MOA, 2), "drift_cm": round(drift * 100, 1),
                     "drift_mrad": round(drift / x * 1000, 2), "drift_moa": round(drift / x * 1000 * MRAD_TO_MOA, 2),
                     "lag_s": round(lag, 4), "time_s": round(r["t"], 3), "velocity_ms": round(r["v"], 1),
                     "energy_j": round(0.5 * bullet_kg * r["v"] ** 2) if bullet_kg else None})
    return rows


# ---------------------------------------------------------------------------------------------
# Speed against temperature
# ---------------------------------------------------------------------------------------------
MIN_POINTS, MIN_SPAN_C = 3, 5.0


def temp_fit(points: list[tuple[float, float]]) -> dict | None:
    """Least-squares line through (temperature C, average velocity m/s) points: {slope (m/s per C), intercept, r2, n, span}.
    None if there aren't enough sessions (3) or they're all within 5 degrees of each other."""
    pts = [(float(t), float(v)) for t, v in points if t is not None and v is not None]
    if len(pts) < MIN_POINTS:
        return None
    n = len(pts)
    mt, mv = sum(t for t, _ in pts) / n, sum(v for _, v in pts) / n
    sxx = sum((t - mt) ** 2 for t, _ in pts)
    span = max(t for t, _ in pts) - min(t for t, _ in pts)
    if span < MIN_SPAN_C or sxx == 0:
        return None
    slope = sum((t - mt) * (v - mv) for t, v in pts) / sxx
    intercept = mv - slope * mt
    ss_tot = sum((v - mv) ** 2 for _, v in pts)
    ss_res = sum((v - (intercept + slope * t)) ** 2 for t, v in pts)
    return {"slope": slope, "intercept": intercept, "r2": round(1 - ss_res / ss_tot, 3) if ss_tot else 1.0, "n": n, "span": round(span, 1)}


def fps_per_degree(slope_ms_per_c: float) -> dict:
    return {"fps_per_c": round(slope_ms_per_c / 0.3048, 2), "fps_per_f": round(slope_ms_per_c / 0.3048 / 1.8, 2)}


def sessions_speed_points(conn, ammo_id: int, rifle_id: int | None = None) -> list[dict]:
    """One point per session that has a temperature and chronograph speeds for this ammo: its average speed (m/s)."""
    rows = conn.execute(
        """SELECT s.session_id, s.shot_on, s.temp_c::float8 AS temp_c, g.velocities::float8[] AS velocities
           FROM shooting_sessions s JOIN shooting_groups g ON g.session_id = s.session_id
           WHERE s.ammo_id = %s AND s.temp_c IS NOT NULL AND g.velocities IS NOT NULL AND (%s::int IS NULL OR s.rifle_id = %s)
           ORDER BY s.shot_on, s.session_id""", (ammo_id, rifle_id, rifle_id)).fetchall()
    by_session: dict = {}
    for r in rows:
        entry = by_session.setdefault(r["session_id"], {"session_id": r["session_id"], "on": r["shot_on"], "temp_c": r["temp_c"], "speeds": []})
        entry["speeds"] += [v for v in r["velocities"] or [] if v]
    return [{"session_id": e["session_id"], "on": e["on"], "temp_c": e["temp_c"], "shots": len(e["speeds"]),
             "avg_ms": round(sum(e["speeds"]) / len(e["speeds"]), 1)} for e in by_session.values() if len(e["speeds"]) >= 2]


def sensitivity(conn, ammo_id: int, rifle_id: int | None = None) -> dict:
    points = sessions_speed_points(conn, ammo_id, rifle_id)
    fit = temp_fit([(p["temp_c"], p["avg_ms"]) for p in points])
    return {"ammo_id": ammo_id, "rifle_id": rifle_id, "points": points, "enough": fit is not None,
            "need": f"Needs {MIN_POINTS} sessions with a temperature and chronograph speeds, at least {MIN_SPAN_C:g} degrees apart.",
            "fit": fit and {**fit, "slope": round(fit["slope"], 3), "intercept": round(fit["intercept"], 1), **fps_per_degree(fit["slope"])}}


@router.get("/shooting/ammo/{ammo_id}/temp-sensitivity")
def ammo_temp_sensitivity(ammo_id: int, rifle_id: int | None = None):
    """How much faster (or slower) this ammo shoots per degree, from your sessions' chronograph speeds."""
    with db() as conn:
        found(conn.execute("SELECT 1 FROM ammo WHERE ammo_id = %s", (ammo_id,)).fetchone(), "Ammunition")
        return sensitivity(conn, ammo_id, rifle_id)


# ---------------------------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------------------------
@router.get("/shooting/ballistics")
def ballistics(rifle_id: int, ammo_id: int, max_m: int = Query(300, ge=50, le=1500), step: int = Query(25, ge=5, le=250),
               at: str | None = Query(None, max_length=200), session_id: int | None = None,
               temp_c: float | None = Query(None, ge=-40, le=60), pressure_hpa: float | None = Query(None, ge=300, le=1100),
               humidity_pct: float | None = Query(None, ge=0, le=100), wind_kmh: float = Query(10, ge=0, le=200),
               zero_temp_c: float | None = Query(None, ge=-40, le=60), zero_pressure_hpa: float | None = Query(None, ge=300, le=1100),
               zero_humidity_pct: float | None = Query(None, ge=0, le=100), mv_ms: float | None = Query(None, gt=0, le=2000),
               bc: float | None = Query(None, gt=0, lt=2), bc_model: str | None = Query(None, pattern="^(G1|G7)$")):
    """The predicted table for a rifle and ammo. Typed values win over the session's, which win over the standard day.
    `at` is extra distances in metres, comma separated (to line up with your DOPE card)."""
    with db() as conn:
        rifle = found(conn.execute("SELECT rifle_id, name, scope_unit, click::float8 AS click, zero_m, sight_height_mm::float8 AS sight "
                                   "FROM rifles WHERE rifle_id = %s", (rifle_id,)).fetchone(), "Rifle")
        ammo = found(conn.execute("SELECT ammo_id, name, bc::float8 AS bc, bc_model, velocity_ms::float8 AS mv, bullet_gr::float8 AS gr "
                                  "FROM ammo WHERE ammo_id = %s", (ammo_id,)).fetchone(), "Ammunition")
        session = found(conn.execute("SELECT temp_c::float8 AS temp_c, pressure_hpa::float8 AS pressure_hpa, humidity_pct, wind_kmh::float8 AS wind "
                                     "FROM shooting_sessions WHERE session_id = %s", (session_id,)).fetchone(), "Session") if session_id else {}
        fit = sensitivity(conn, ammo_id, rifle_id)["fit"]
    bc_value, model, mv = bc or ammo["bc"], bc_model or ammo["bc_model"] or "G1", mv_ms or ammo["mv"]
    if not bc_value or not mv:
        raise HTTPException(422, "The ammo needs a ballistic coefficient and a muzzle velocity (edit it on the Ammo page).")
    if not rifle["zero_m"]:
        raise HTTPException(422, "The rifle needs a zero distance (edit it on the Rifles page).")
    temp = temp_c if temp_c is not None else session.get("temp_c")
    pressure = pressure_hpa if pressure_hpa is not None else session.get("pressure_hpa")
    humidity = humidity_pct if humidity_pct is not None else session.get("humidity_pct")
    notes = []
    shot_mv = mv
    if fit and temp is not None and mv_ms is None:
        shot_mv = fit["intercept"] + fit["slope"] * temp
        notes.append(f"Muzzle velocity {shot_mv:.0f} m/s at {temp:g} C, from your chronograph sessions ({fit['fps_per_f']:+g} fps per F).")
    shot_air = atmosphere(temp, pressure, humidity)
    zero_air = atmosphere(zero_temp_c, zero_pressure_hpa, zero_humidity_pct)
    if not shot_air["standard"] and zero_air["standard"] and zero_temp_c is None:
        notes.append("Zeroed on a standard day (15 C, 1013 hPa) unless you say where it was zeroed.")
    sight = rifle["sight"] or DEFAULT_SIGHT_MM
    if not rifle["sight"]:
        notes.append(f"No sight height on the rifle: using {DEFAULT_SIGHT_MM:g} mm.")
    distances = set(range(step, max_m + 1, step))
    for part in (at or "").split(","):
        if part.strip().isdigit() and 1 <= int(part) <= 1500:
            distances.add(int(part))
    rows = trajectory(shot_mv, bc_value, model, rifle["zero_m"], sight, sorted(distances), shot_air, zero_air,
                      wind_ms=wind_kmh / 3.6, bullet_kg=ammo["gr"] * GRAIN_KG if ammo["gr"] else None, mv_zero=mv)
    unit = rifle["scope_unit"] or "MOA"
    for r in rows:
        r["elevation"] = r["elev_mrad"] if unit == "MIL" else r["elev_moa"]
        r["wind"] = r["drift_mrad"] if unit == "MIL" else r["drift_moa"]
        r["wind10"] = round(r["wind"] * 10 / wind_kmh, 2) if wind_kmh else None
    return {"rifle": {k: rifle[k] for k in ("rifle_id", "name", "click", "zero_m")} | {"sight_mm": sight}, "unit": unit,
            "ammo": {"ammo_id": ammo_id, "name": ammo["name"], "bc": bc_value, "bc_model": model, "mv_ms": round(shot_mv, 1)},
            "wind_kmh": wind_kmh, "air": {k: v for k, v in shot_air.items() if k != "rho"},
            "zero_air": {k: v for k, v in zero_air.items() if k != "rho"}, "rows": rows, "notes": notes,
            "temp_fit": fit}
