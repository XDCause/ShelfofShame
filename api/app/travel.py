"""Travel: trips - ideas, planned, happening now and remembered - and places (77_travel.sql). A trip's bookings,
day plan, money, packing, journal and photos are in travel_trip.py; exchange rates in frankfurter.py.

    GET  /travel/lists                     the choices (kinds, booking kinds, categories, currencies...)
    GET / PUT /travel/settings             passport expiry
    GET  /travel/summary                   the dashboard: now / next trip, this year, countries, bucket list...
    GET / POST /travel/trips               every trip (now, upcoming, ideas, past, cancelled)
    GET / PATCH / DELETE /travel/trips/{id} (+ /photo: its cover) - GET has everything (see trip_detail)
    GET  /travel/places                    every place (the map): a trip's stops and the bucket list
    POST /travel/places, PATCH / DELETE /travel/places/{id}
    PUT  /travel/trips/{id}/stops          the stops' order (a road trip's route)
    GET  /travel/find-place?q=             towns and cities by name (Open-Meteo's place search), with where they are
    GET  /travel/countries                 been (from trips, places and ones you add) and want
    PUT / DELETE /travel/countries/{code}

A trip's phase comes from its dates: idea (no dates, or status Idea), upcoming, now, past - or cancelled. Places on a
trip that's over count as Been. Trips show on the calendar (every day, and timed bookings) and in the activity feed.
"""
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from . import frankfurter, openmeteo
from .db import MODULE_IDS, db, found, insert_row, tidy_text, update_row
from .images import add_photo_routes

router = APIRouter(prefix="/api", tags=["travel"])

KINDS = ["Overseas", "Domestic", "Road trip", "Camping"]
STATUSES = ["Idea", "Planned", "Cancelled"]
BOOKING_KINDS = ["Flight", "Stay", "Car hire", "Train", "Bus", "Ferry", "Tour", "Event", "Campsite", "Insurance", "Other"]
CATEGORIES = ["Stay", "Transport", "Food", "Activities", "Shopping", "Other"]
PLACE_KINDS = ["City", "Sight", "Food", "Stay", "Nature", "Beach", "Campsite", "Activity", "Other"]
PLACE_STATUSES = ["Want", "Planned", "Been"]
GROUPS = ["Documents", "Clothes", "Toiletries", "Health", "Tech", "Gear", "Other"]
HOBBIES = [m for m in MODULE_IDS if m not in ("travel", "car")]
# A booking's money goes in one of the spending categories.
BOOKING_CATEGORY = {"Flight": "Transport", "Car hire": "Transport", "Train": "Transport", "Bus": "Transport",
                    "Ferry": "Transport", "Stay": "Stay", "Campsite": "Stay", "Tour": "Activities", "Event": "Activities",
                    "Insurance": "Other", "Other": "Other"}
# When the exchange rates can't be asked (or in tests): the usual ones.
COMMON_CURRENCIES = ["AUD", "NZD", "USD", "EUR", "GBP", "JPY", "SGD", "THB", "IDR", "KRW", "CNY", "HKD", "CAD", "MYR", "PHP",
                     "INR", "CHF"]
PASSPORT_MARGIN = timedelta(days=183)   # many countries want 6 months left on it when you arrive


def _lit(values) -> str:
    return "^(" + "|".join(values) + ")$"


def currencies() -> list[str]:
    try:
        published = sorted(frankfurter.rates()["aud_per"])
    except frankfurter.RatesError:
        return COMMON_CURRENCIES
    return ["AUD"] + [c for c in published if c != "AUD"]


@router.get("/travel/lists")
def lists():
    return {"kinds": KINDS, "statuses": STATUSES, "booking_kinds": BOOKING_KINDS, "categories": CATEGORIES,
            "place_kinds": PLACE_KINDS, "place_statuses": PLACE_STATUSES, "groups": GROUPS, "hobbies": HOBBIES,
            "currencies": currencies(), "booking_category": BOOKING_CATEGORY}


# ---------------------------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------------------------
class SettingsIn(BaseModel):
    passport_expires: date | None = None


def settings(conn) -> dict:
    return conn.execute("SELECT passport_expires, passport_expires - current_date AS passport_days "
                        "FROM travel_settings WHERE id = 1").fetchone()


@router.get("/travel/settings")
def get_settings():
    with db() as conn:
        return settings(conn)


@router.put("/travel/settings")
def put_settings(body: SettingsIn):
    with db() as conn:
        conn.execute("UPDATE travel_settings SET passport_expires = %s, updated_at = now() WHERE id = 1",
                     (body.passport_expires,))
        return settings(conn)


# ---------------------------------------------------------------------------------------------
# Trips
# ---------------------------------------------------------------------------------------------
class TripFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(KINDS))
    status: str | None = Field(None, pattern=_lit(STATUSES))
    hobby: str | None = Field(None, pattern=_lit(HOBBIES))
    start_date: date | None = None
    end_date: date | None = None
    destination: str | None = Field(None, max_length=200)
    countries: list[str] | None = Field(None, max_length=60)
    budget: float | None = Field(None, ge=0, le=10_000_000)
    rating: int | None = Field(None, ge=1, le=5)
    highlights: str | None = Field(None, max_length=10000)
    notes: str | None = Field(None, max_length=10000)


class TripIn(TripFields):
    name: str = Field(min_length=1, max_length=120)


class TripPatch(TripFields):
    name: str | None = Field(None, min_length=1, max_length=120)


PHASE = """CASE WHEN t.status = 'Cancelled' THEN 'cancelled'
            WHEN t.status = 'Idea' OR t.start_date IS NULL THEN 'idea'
            WHEN current_date < t.start_date THEN 'upcoming'
            WHEN current_date <= COALESCE(t.end_date, t.start_date) THEN 'now'
            ELSE 'past' END"""
SPENT = """(SELECT COALESCE(sum(b.cost * b.rate), 0) FROM trip_bookings b WHERE b.trip_id = t.trip_id)
         + (SELECT COALESCE(sum(e.amount * e.rate), 0) FROM trip_expenses e WHERE e.trip_id = t.trip_id)"""
TRIP_SELECT = f"""
SELECT t.trip_id, t.name, t.kind, t.status, t.hobby, t.start_date, t.end_date, t.destination, t.countries,
       t.budget::float8 AS budget, t.rates, t.rating, t.highlights, t.notes, t.created_at,
       {PHASE} AS phase,
       COALESCE(t.end_date, t.start_date) - t.start_date + 1 AS days,
       t.start_date - current_date AS starts_in,
       current_date - t.start_date + 1 AS day_number,
       round(({SPENT})::numeric, 2)::float8 AS spent,
       (SELECT count(*) FROM trip_bookings b WHERE b.trip_id = t.trip_id)::int AS bookings_count,
       (SELECT count(*) FROM trip_places p WHERE p.trip_id = t.trip_id)::int AS places_count,
       (SELECT count(*) FROM trip_packing k WHERE k.trip_id = t.trip_id)::int AS packing_count,
       (SELECT count(*) FROM trip_packing k WHERE k.trip_id = t.trip_id AND k.packed)::int AS packed_count,
       (SELECT count(*) FROM trip_photos ph WHERE ph.trip_id = t.trip_id)::int AS photos_count,
       CASE WHEN t.photo IS NOT NULL THEN '/api/travel/trips/' || t.trip_id || '/photo?v='
                 || (extract(epoch FROM t.photo_updated) * 1000)::bigint
            ELSE (SELECT '/api/travel/photos/' || ph.photo_id FROM trip_photos ph WHERE ph.trip_id = t.trip_id
                  ORDER BY ph.taken_at NULLS LAST, ph.photo_id LIMIT 1) END AS photo_url,
       t.photo IS NOT NULL AS has_cover
FROM trips t"""
# Now first, then the next ones soonest first, ideas, the past newest first, cancelled last.
TRIP_ORDER = """ORDER BY CASE phase WHEN 'now' THEN 0 WHEN 'upcoming' THEN 1 WHEN 'idea' THEN 2 WHEN 'past' THEN 3 ELSE 4 END,
         CASE WHEN phase IN ('now', 'upcoming') THEN start_date END,
         CASE WHEN phase NOT IN ('now', 'upcoming') THEN start_date END DESC NULLS LAST, created_at DESC"""


def _check_trip(data: dict):
    if "countries" in data:
        codes = [c.strip().upper() for c in data["countries"] or [] if c and c.strip()]
        if any(len(c) != 2 or not c.isalpha() for c in codes):
            raise HTTPException(422, "Countries are two-letter codes (JP, NZ).")
        data["countries"] = list(dict.fromkeys(codes))
    for required in ("name", "kind", "status"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.capitalize()} can't be empty.")


@router.get("/travel/trips")
def list_trips(phase: Literal["now", "upcoming", "idea", "past", "cancelled"] | None = None):
    with db() as conn:
        rows = conn.execute(f"SELECT * FROM ({TRIP_SELECT}) x" + (" WHERE phase = %s " if phase else " ") + TRIP_ORDER,
                            (phase,) if phase else ()).fetchall()
    return rows


@router.post("/travel/trips", status_code=201)
def add_trip(body: TripIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    _check_trip(data)
    with db() as conn:
        _dates_ok(data.get("start_date"), data.get("end_date"))
        trip_id = insert_row(conn, "trips", data, "trip_id")
        return trip_detail(conn, trip_id)


def _dates_ok(start, end):
    if start and end and end < start:
        raise HTTPException(422, "The trip has to end on or after the day it starts.")


@router.get("/travel/trips/{trip_id}")
def get_trip(trip_id: int):
    with db() as conn:
        return trip_detail(conn, trip_id, weather=True)


@router.patch("/travel/trips/{trip_id}")
def update_trip(trip_id: int, body: TripPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _check_trip(data)
    with db() as conn:
        old = found(conn.execute("SELECT start_date, end_date FROM trips WHERE trip_id = %s", (trip_id,)).fetchone(), "Trip")
        _dates_ok(data.get("start_date", old["start_date"]), data.get("end_date", old["end_date"]))
        update_row(conn, "trips", "trip_id", trip_id, data)
        conn.execute("UPDATE trips SET updated_at = now() WHERE trip_id = %s", (trip_id,))
        return trip_detail(conn, trip_id)


@router.delete("/travel/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int):
    """A trip and everything on it (bookings, plan, money, packing, its places, journal and photos)."""
    with db() as conn:
        found(conn.execute("DELETE FROM trips WHERE trip_id = %s RETURNING trip_id", (trip_id,)).fetchone(), "Trip")
    return Response(status_code=204)


add_photo_routes(router, "/travel/trips", "trips", "trip_id", "Trip")


def trip_row(conn, trip_id: int) -> dict:
    return found(conn.execute(TRIP_SELECT + " WHERE t.trip_id = %s", (trip_id,)).fetchone(), "Trip")


def trip_detail(conn, trip_id: int, weather: bool = False) -> dict:
    """A trip with everything on it, what it's cost against its budget, what needs doing, and (when it's on or about
    to be, and weather=True) the forecast where it is."""
    t = trip_row(conn, trip_id)
    t["bookings"] = conn.execute("""
        SELECT booking_id, kind, title, provider, reference, starts_at, ends_at, from_place, to_place, address,
               cost::float8 AS cost, currency, rate::float8 AS rate, round(cost * rate, 2)::float8 AS cost_aud, paid, link, notes
        FROM trip_bookings WHERE trip_id = %s ORDER BY starts_at NULLS LAST, booking_id""", (trip_id,)).fetchall()
    for b in t["bookings"]:
        b["category"] = BOOKING_CATEGORY[b["kind"]]
    t["plan"] = conn.execute("""
        SELECT i.item_id, i.day, i.at, i.title, i.place_id, p.name AS place_name, i.notes, i.done
        FROM trip_plan i LEFT JOIN trip_places p ON p.place_id = i.place_id
        WHERE i.trip_id = %s ORDER BY i.day NULLS FIRST, i.at NULLS LAST, i.item_id""", (trip_id,)).fetchall()
    t["expenses"] = conn.execute("""
        SELECT expense_id, spent_on, category, what, amount::float8 AS amount, currency, rate::float8 AS rate,
               round(amount * rate, 2)::float8 AS aud
        FROM trip_expenses WHERE trip_id = %s ORDER BY spent_on DESC, expense_id DESC""", (trip_id,)).fetchall()
    t["packing"] = conn.execute("""
        SELECT k.item_id, k.name, k.grp, k.qty, k.packed, k.gear_id, g.hobby AS gear_hobby
        FROM trip_packing k LEFT JOIN gear g ON g.gear_id = k.gear_id
        WHERE k.trip_id = %s ORDER BY array_position(%s::text[], k.grp), lower(k.name)""", (trip_id, GROUPS)).fetchall()
    t["places"] = conn.execute(PLACE_SELECT + " WHERE p.trip_id = %s ORDER BY p.stop_order NULLS LAST, p.place_id",
                               (trip_id,)).fetchall()
    t["entries"] = conn.execute("SELECT entry_id, day, text, updated_at FROM trip_entries WHERE trip_id = %s ORDER BY day",
                                (trip_id,)).fetchall()
    t["photos"] = conn.execute(PHOTO_SELECT + " WHERE trip_id = %s ORDER BY day NULLS LAST, taken_at NULLS LAST, photo_id",
                               (trip_id,)).fetchall()
    t["money"] = money(t)
    t["passport"] = settings(conn)
    t["warnings"] = warnings(t)
    t["weather"] = forecast_for(t) if weather else None
    return t


PHOTO_SELECT = """SELECT photo_id, trip_id, '/api/travel/photos/' || photo_id AS url, day, taken_at,
       lat::float8 AS lat, lon::float8 AS lon, caption FROM trip_photos"""


def money(t: dict) -> dict:
    """Spent (bookings + money spent there, in AUD) by category, against the budget; what's still to pay."""
    by = {c: 0.0 for c in CATEGORIES}
    for b in t["bookings"]:
        by[b["category"]] += b["cost_aud"] or 0
    for e in t["expenses"]:
        by[e["category"]] += e["aud"] or 0
    spent = round(sum(by.values()), 2)
    unpaid = round(sum(b["cost_aud"] or 0 for b in t["bookings"] if not b["paid"]), 2)
    days = t["days"] or 0
    return {"budget": t["budget"], "spent": spent, "left": round(t["budget"] - spent, 2) if t["budget"] is not None else None,
            "by_category": [{"category": c, "aud": round(v, 2)} for c, v in by.items() if v],
            "unpaid": unpaid, "per_day": round(spent / days, 2) if days and spent else None,
            "currencies": sorted(({b["currency"] for b in t["bookings"]} | {e["currency"] for e in t["expenses"]}) - {"AUD"})}


def warnings(t: dict) -> list[str]:
    """What needs doing before the trip (or while it's on): passport, unpaid bookings, to-dos, packing, budget."""
    out = []
    if t["phase"] not in ("upcoming", "now"):
        return out
    passport = t["passport"]["passport_expires"]
    if t["kind"] == "Overseas":
        home = t["end_date"] or t["start_date"]
        if passport is None:
            out.append("When does your passport expire? Set it on the Travel dashboard so it can be checked.")
        elif passport < home:
            out.append(f"Your passport expires on {passport:%d %b %Y} - before you come home.")
        elif passport < home + PASSPORT_MARGIN:
            out.append(f"Your passport expires on {passport:%d %b %Y}, under 6 months after you come home: "
                       "many countries won't let you in. Check the rules where you're going.")
    soon = t["phase"] == "now" or (t["starts_in"] is not None and t["starts_in"] <= 14)
    unpaid = [b for b in t["bookings"] if not b["paid"] and b["cost"]]
    if soon and unpaid:
        out.append(f"{len(unpaid)} booking{'s' if len(unpaid) > 1 else ''} not marked paid.")
    todo = [i for i in t["plan"] if i["day"] is None and not i["done"]]
    if soon and todo and t["phase"] == "upcoming":
        out.append(f"{len(todo)} thing{'s' if len(todo) > 1 else ''} to do before you go.")
    if t["phase"] == "upcoming" and t["starts_in"] <= 3 and t["packing_count"] and t["packed_count"] < t["packing_count"]:
        out.append(f"Packed {t['packed_count']} of {t['packing_count']}.")
    if t["budget"] is not None and t["money"]["spent"] > t["budget"]:
        out.append(f"Over budget by ${t['money']['spent'] - t['budget']:,.2f}.")
    return out


def forecast_for(t: dict) -> dict | None:
    """The next 3 days' weather where the trip is - while it's on, or from 2 days before. Its stops in order: the
    one planned for today (or the first)."""
    if not (t["phase"] == "now" or (t["phase"] == "upcoming" and t["starts_in"] <= 2)):
        return None
    spots = [p for p in t["places"] if p["lat"] is not None]
    if not spots:
        return None
    today = date.today()
    spot = next((p for p in spots if p["visit_on"] == today), spots[0])
    try:
        return {"place": spot["name"], "days": openmeteo.forecast(spot["lat"], spot["lon"])}
    except openmeteo.WeatherError:
        return None


# ---------------------------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------------------------


# shown: what the map says - a planned place on a trip that's over was Been.
PLACE_SELECT = f"""
SELECT p.place_id, p.trip_id, t.name AS trip_name, p.name, p.kind, p.status, p.country, p.region,
       p.lat::float8 AS lat, p.lon::float8 AS lon, p.stop_order, p.visit_on, p.rating, p.link, p.notes,
       CASE WHEN p.status = 'Planned' AND t.trip_id IS NOT NULL AND ({PHASE}) = 'past' THEN 'Been'
            WHEN p.status = 'Planned' AND t.trip_id IS NOT NULL AND ({PHASE}) IN ('idea', 'cancelled') THEN 'Want'
            ELSE p.status END AS shown
FROM trip_places p LEFT JOIN trips t ON t.trip_id = p.trip_id"""


# ---------------------------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------------------------


def countries(conn) -> dict:
    """Been: ones you've added, every country of a trip that's started, and every place you've been. Want: ones
    you've added, and countries of places on your bucket list - unless you've been."""
    trips = conn.execute(f"""SELECT unnest(t.countries) AS code, t.start_date FROM trips t
                             WHERE ({PHASE}) IN ('now', 'past')""").fetchall()
    places = conn.execute(f"SELECT country, shown FROM ({PLACE_SELECT}) x WHERE country IS NOT NULL").fetchall()
    mine = {r["code"]: r for r in conn.execute("SELECT * FROM travel_countries").fetchall()}
    been: dict[str, dict] = {}
    for r in trips:
        c = been.setdefault(r["code"], {"code": r["code"], "trips": 0, "places": 0, "first_year": None, "added": False})
        c["trips"] += 1
        if r["start_date"] and (c["first_year"] is None or r["start_date"].year < c["first_year"]):
            c["first_year"] = r["start_date"].year
    for p in places:
        if p["shown"] == "Been":
            been.setdefault(p["country"], {"code": p["country"], "trips": 0, "places": 0, "first_year": None, "added": False})["places"] += 1
    for code, r in mine.items():
        if r["status"] == "Been":
            c = been.setdefault(code, {"code": code, "trips": 0, "places": 0, "first_year": None, "added": False})
            c["added"] = True
            c["notes"] = r["notes"]
            if r["first_year"] and (c["first_year"] is None or r["first_year"] < c["first_year"]):
                c["first_year"] = r["first_year"]
    want = {code: {"code": code, "added": True, "places": 0, "notes": r["notes"]}
            for code, r in mine.items() if r["status"] == "Want" and code not in been}
    for p in places:
        if p["shown"] == "Want" and p["country"] not in been:
            want.setdefault(p["country"], {"code": p["country"], "added": False, "places": 0})["places"] += 1
    return {"been": sorted(been.values(), key=lambda c: (c["first_year"] or 9999, c["code"])),
            "want": sorted(want.values(), key=lambda c: c["code"])}


# ---------------------------------------------------------------------------------------------
# The dashboard
# ---------------------------------------------------------------------------------------------
@router.get("/travel/summary")
def summary():
    year = date.today().year
    with db() as conn:
        trips = conn.execute(f"SELECT * FROM ({TRIP_SELECT}) x {TRIP_ORDER}").fetchall()
        c = countries(conn)
        been_places = conn.execute(f"SELECT count(*) AS n FROM ({PLACE_SELECT}) x WHERE shown = 'Been'").fetchone()["n"]
        want_places = conn.execute(f"SELECT count(*) AS n FROM ({PLACE_SELECT}) x WHERE shown = 'Want'").fetchone()["n"]
        passport = settings(conn)
    started = [t for t in trips if t["phase"] in ("now", "past")]
    this_year = [t for t in started if t["start_date"].year == year]

    def light(t):
        return {k: t[k] for k in ("trip_id", "name", "kind", "hobby", "start_date", "end_date", "destination", "countries",
                                  "phase", "days", "starts_in", "day_number", "photo_url", "budget", "spent", "rating",
                                  "packing_count", "packed_count")}
    years = {}
    for t in started:
        y = years.setdefault(t["start_date"].year, {"year": t["start_date"].year, "trips": 0, "days": 0, "spent": 0.0})
        y["trips"] += 1
        y["days"] += t["days"] or 0
        y["spent"] += t["spent"] or 0
    passport_warning = None
    if passport["passport_expires"] and passport["passport_days"] < 365:
        passport_warning = (f"Your passport expired on {passport['passport_expires']:%d %b %Y}." if passport["passport_days"] < 0 else
                            f"Your passport expires on {passport['passport_expires']:%d %b %Y} - renewing takes weeks.")
    return {
        "year": year,
        "now": [light(t) for t in trips if t["phase"] == "now"],
        "upcoming": [light(t) for t in trips if t["phase"] == "upcoming"],
        "ideas": [light(t) for t in trips if t["phase"] == "idea"],
        "recent": [light(t) for t in trips if t["phase"] == "past"][:5],
        "this_year": {"trips": len(this_year), "days": sum(t["days"] or 0 for t in this_year),
                      "spent": round(sum(t["spent"] or 0 for t in this_year), 2)},
        "all_time": {"trips": len(started), "days": sum(t["days"] or 0 for t in started)},
        "countries_been": len(c["been"]), "countries_want": len(c["want"]),
        "places_been": been_places, "bucket_list": want_places,
        "years": [{**y, "spent": round(y["spent"], 2)} for y in sorted(years.values(), key=lambda y: y["year"])][-8:],
        "passport": passport, "passport_warning": passport_warning,
    }


# ---------------------------------------------------------------------------------------------
# The calendar
# ---------------------------------------------------------------------------------------------
def _entry(key: str, trip: dict, day: date, title: str, at=None, until=None, location=None) -> dict:
    return {"event_id": key, "trip_id": trip["trip_id"], "day": day, "title": title, "hobby": "travel",
            "start_time": at, "end_time": until, "location": location, "notes": None, "repeats": "never",
            "repeat_until": None, "starts_on": trip["start_date"], "logged_id": None}


def calendar_entries(conn, start: date, end: date, first_day_only: bool = False) -> list[dict]:
    """Trips on the calendar: every day of a trip (or just its first, for Coming up), and its timed bookings - a
    flight's departure, a stay's check-in and check-out, a hire car's pick-up and return."""
    trips = conn.execute("""SELECT trip_id, name, start_date, COALESCE(end_date, start_date) AS end_date, destination
                            FROM trips WHERE status = 'Planned' AND start_date IS NOT NULL
                            AND start_date <= %s AND COALESCE(end_date, start_date) >= %s""", (end, start)).fetchall()
    out = []
    for t in trips:
        n = (t["end_date"] - t["start_date"]).days + 1
        day = max(start, t["start_date"])
        while day <= min(end, t["end_date"]):
            if not first_day_only or day == t["start_date"]:
                k = (day - t["start_date"]).days + 1
                title = t["name"] if n == 1 else (f"{t['name']} starts" if first_day_only else f"{t['name']} · day {k} of {n}")
                out.append(_entry(f"trip-{t['trip_id']}-{day}", t, day, title, location=t["destination"]))
            day += timedelta(days=1)
    bookings = conn.execute("""
        SELECT b.booking_id, b.kind, b.title, b.starts_at, b.ends_at, b.from_place, b.to_place, b.address,
               t.trip_id, t.start_date
        FROM trip_bookings b JOIN trips t USING (trip_id)
        WHERE t.status <> 'Cancelled' AND ((b.starts_at::date BETWEEN %(s)s AND %(e)s) OR (b.ends_at::date BETWEEN %(s)s AND %(e)s))""",
        {"s": start, "e": end}).fetchall()
    stays = {"Stay": ("Check in", "Check out"), "Campsite": ("Check in", "Check out"), "Car hire": ("Pick up", "Return")}
    for b in bookings:
        where = " → ".join(filter(None, [b["from_place"], b["to_place"]])) or b["address"]
        first, last = stays.get(b["kind"], (b["kind"], None))
        if b["starts_at"] and start <= b["starts_at"].date() <= end:
            out.append(_entry(f"booking-{b['booking_id']}", b, b["starts_at"].date(), f"{first}: {b['title']}",
                              at=_time(b["starts_at"]), until=None if last else _time(b["ends_at"], b["starts_at"]), location=where))
        if last and b["ends_at"] and start <= b["ends_at"].date() <= end:
            out.append(_entry(f"booking-{b['booking_id']}-end", b, b["ends_at"].date(), f"{last}: {b['title']}",
                              at=_time(b["ends_at"]), location=where))
    return out


def _time(when: datetime | None, same_day_as: datetime | None = None):
    """The time of day, unless it's midnight (a date with no time); with same_day_as, only on that day."""
    if when is None or (same_day_as is not None and when.date() != same_day_as.date()):
        return None
    return None if (when.hour, when.minute) == (0, 0) else when.time()
