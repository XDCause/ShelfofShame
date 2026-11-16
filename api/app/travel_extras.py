"""Travel extras: splitting a trip's costs between people, and the day-by-day map.

Costs (the money tab's "spent there" and the bookings that have a cost) can say who paid and who shares them. Money
is worked in AUD (each cost keeps the rate it was entered with: travel_trip.py), so a yen meal and a euro hotel
add up. Costs with nobody paid_by are left out. A shared cost with no one picked is shared by everyone on the trip.

    GET    /travel/trips/{id}/split          ?show=JPY: people, every cost, what each person paid and owes,
                                             and "who pays who" with the fewest payments (shown in AUD, or in `show`)
    POST   /travel/trips/{id}/people         {name}: someone on the trip (answers with the split, like all of these)
    PATCH  /travel/people/{id}               {name}
    DELETE /travel/people/{id}               (what they paid becomes unassigned; they drop out of shares)
    PUT    /travel/expenses/{id}/split       {paid_by, shared_by: [person ids]} (paid_by null = not split)
    PUT    /travel/bookings/{id}/split       the same for a booking's cost
    GET    /travel/trips/{id}/day-map        each day's planned places (with a position) in order, and the distance
                                             between stops: straight-line, plus a simple road and travel-time estimate
"""
from datetime import date
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .db import db, found
from .travel import trip_row
from .travel_trip import rate_for

router = APIRouter(prefix="/api", tags=["travel"])

KINDS = {"expense": ("trip_expenses", "expense_id", "trip_expense_shares"),
         "booking": ("trip_bookings", "booking_id", "trip_booking_shares")}


# ---------------------------------------------------------------------------------------------
# The sums (pure: no database), tested in test_travel_extras.py
# ---------------------------------------------------------------------------------------------
def split_cents(total: int, people: list[int]) -> dict[int, int]:
    """A cost shared equally: each person's cents, the odd cents going to the first people (they add up exactly)."""
    people = sorted(people)
    if not people:
        return {}
    each, odd = divmod(total, len(people))
    return {p: each + (1 if i < odd else 0) for i, p in enumerate(people)}


def settle(net: dict[int, int]) -> list[tuple[int, int, int]]:
    """Who pays whom (from, to, cents) so everyone ends level. net: cents each person is owed (+) or owes (-), adding
    to 0. First, pairs whose amounts match exactly pay each other (one payment settles both); then the biggest debt
    pays the biggest credit, again and again: at most (people - 1) payments."""
    owe = {p: -n for p, n in net.items() if n < 0}
    owed = {p: n for p, n in net.items() if n > 0}
    pays = []
    for d in sorted(owe):
        match = next((c for c in sorted(owed) if owed[c] == owe[d]), None)
        if match is not None:
            pays.append((d, match, owe.pop(d)))
            del owed[match]
    while owe and owed:
        d = max(owe, key=lambda p: (owe[p], -p))
        c = max(owed, key=lambda p: (owed[p], -p))
        amount = min(owe[d], owed[c])
        pays.append((d, c, amount))
        owe[d] -= amount
        owed[c] -= amount
        if not owe[d]:
            del owe[d]
        if not owed[c]:
            del owed[c]
    return pays


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line (great circle) kilometres between two (lat, lon) points."""
    (la1, lo1), (la2, lo2) = a, b
    h = sin(radians(la2 - la1) / 2) ** 2 + cos(radians(la1)) * cos(radians(la2)) * sin(radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(h))


ROAD_FACTOR = 1.3        # roads wind: a straight line is about this much shorter than the drive
DRIVE_KMH = 50           # a day's average driving with towns and traffic
WALK_KMH = 4.8


def leg(a: dict, b: dict) -> dict:
    km = km_between((a["lat"], a["lon"]), (b["lat"], b["lon"]))
    road = km * ROAD_FACTOR
    return {"from": a["name"], "to": b["name"], "km": round(km, 1), "road_km": round(road, 1),
            "walk_min": round(road / WALK_KMH * 60), "drive_min": max(1, round(road / DRIVE_KMH * 60))}


# ---------------------------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------------------------
class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class SplitIn(BaseModel):
    paid_by: int | None = Field(None, ge=1, le=2_000_000_000)
    shared_by: list[int] = Field(default_factory=list, max_length=50)


def costs(conn, trip_id: int) -> list[dict]:
    """Every cost that could be split: expenses and bookings with a price, in AUD, with who paid and who's picked."""
    out = []
    for e in conn.execute("""SELECT e.expense_id AS id, e.spent_on AS day, COALESCE(NULLIF(e.what, ''), e.category) AS title, e.amount::float8 AS amount,
                                    e.currency, round(e.amount * e.rate * 100)::int AS cents, e.paid_by,
                                    COALESCE((SELECT array_agg(s.person_id ORDER BY s.person_id) FROM trip_expense_shares s
                                              WHERE s.expense_id = e.expense_id), '{}') AS shared_by
                             FROM trip_expenses e WHERE e.trip_id = %s ORDER BY e.spent_on, e.expense_id""", (trip_id,)).fetchall():
        out.append({"kind": "expense", **e})
    for b in conn.execute("""SELECT b.booking_id AS id, b.starts_at::date AS day, b.title, b.cost::float8 AS amount, b.currency,
                                    round(b.cost * b.rate * 100)::int AS cents, b.paid_by,
                                    COALESCE((SELECT array_agg(s.person_id ORDER BY s.person_id) FROM trip_booking_shares s
                                              WHERE s.booking_id = b.booking_id), '{}') AS shared_by
                             FROM trip_bookings b WHERE b.trip_id = %s AND b.cost IS NOT NULL
                             ORDER BY b.starts_at NULLS LAST, b.booking_id""", (trip_id,)).fetchall():
        out.append({"kind": "booking", **b})
    for c in out:
        c["aud"] = c["cents"] / 100
    return out


def split_of(conn, trip_id: int, show: str | None = None) -> dict:
    trip_row(conn, trip_id)
    people = conn.execute("SELECT person_id, name FROM trip_people WHERE trip_id = %s ORDER BY person_id", (trip_id,)).fetchall()
    ids = [p["person_id"] for p in people]
    items = costs(conn, trip_id)
    paid = dict.fromkeys(ids, 0)
    owes = dict.fromkeys(ids, 0)
    counted = 0
    for c in items:
        c["everyone"] = not c["shared_by"]
        if c["paid_by"] in paid:
            counted += 1
            paid[c["paid_by"]] += c["cents"]
            for p, cents in split_cents(c["cents"], c["shared_by"] or ids).items():
                owes[p] += cents
    names = {p["person_id"]: p["name"] for p in people}
    net = {p: paid[p] - owes[p] for p in ids}
    currency, rate = "AUD", 1.0
    if show and show.upper() != "AUD":
        currency = show.upper()
        rate = rate_for(conn, trip_id, currency)
    shown = lambda cents: round(cents / 100 / rate, 2)    # noqa: E731  (AUD cents -> the chosen currency)
    return {
        "trip_id": trip_id, "people": people, "items": items, "currency": currency, "counted": counted,
        "unassigned": sum(1 for c in items if c["paid_by"] not in paid),
        "balances": [{"person_id": p, "name": names[p], "paid": shown(paid[p]), "share": shown(owes[p]), "net": shown(net[p])} for p in ids],
        "settle": [{"from_id": d, "from": names[d], "to_id": c, "to": names[c], "amount": shown(a), "aud": a / 100}
                   for d, c, a in settle(net)],
        "total": shown(sum(c["cents"] for c in items if c["paid_by"] in paid)),
    }


@router.get("/travel/trips/{trip_id}/split")
def get_split(trip_id: int, show: str | None = Query(None, pattern="^[A-Za-z]{3}$")):
    with db() as conn:
        return split_of(conn, trip_id, show)


@router.post("/travel/trips/{trip_id}/people", status_code=201)
def add_person(trip_id: int, body: PersonIn):
    name = " ".join(body.name.split())
    with db() as conn:
        trip_row(conn, trip_id)
        if conn.execute("SELECT 1 FROM trip_people WHERE trip_id = %s AND lower(name) = lower(%s)", (trip_id, name)).fetchone():
            raise HTTPException(409, f"{name} is already on this trip.")
        conn.execute("INSERT INTO trip_people (trip_id, name) VALUES (%s, %s)", (trip_id, name))
        return split_of(conn, trip_id)


@router.patch("/travel/people/{person_id}")
def rename_person(person_id: int, body: PersonIn):
    name = " ".join(body.name.split())
    with db() as conn:
        p = found(conn.execute("SELECT trip_id FROM trip_people WHERE person_id = %s", (person_id,)).fetchone(), "Person")
        if conn.execute("SELECT 1 FROM trip_people WHERE trip_id = %s AND lower(name) = lower(%s) AND person_id <> %s",
                        (p["trip_id"], name, person_id)).fetchone():
            raise HTTPException(409, f"{name} is already on this trip.")
        conn.execute("UPDATE trip_people SET name = %s WHERE person_id = %s", (name, person_id))
        return split_of(conn, p["trip_id"])


@router.delete("/travel/people/{person_id}")
def delete_person(person_id: int):
    with db() as conn:
        p = found(conn.execute("DELETE FROM trip_people WHERE person_id = %s RETURNING trip_id", (person_id,)).fetchone(), "Person")
        return split_of(conn, p["trip_id"])


def set_split(conn, kind: str, cost_id: int, body: SplitIn) -> dict:
    table, id_col, shares = KINDS[kind]
    row = found(conn.execute(f"SELECT trip_id FROM {table} WHERE {id_col} = %s", (cost_id,)).fetchone(), kind.capitalize())
    trip_id = row["trip_id"]
    wanted = set(body.shared_by) | ({body.paid_by} if body.paid_by else set())
    known = {r["person_id"] for r in conn.execute("SELECT person_id FROM trip_people WHERE trip_id = %s", (trip_id,)).fetchall()}
    if wanted - known:
        raise HTTPException(422, "Those people aren't on this trip.")
    conn.execute(f"UPDATE {table} SET paid_by = %s WHERE {id_col} = %s", (body.paid_by, cost_id))
    conn.execute(f"DELETE FROM {shares} WHERE {id_col} = %s", (cost_id,))
    if body.paid_by:
        for p in sorted(set(body.shared_by)):
            conn.execute(f"INSERT INTO {shares} ({id_col}, person_id) VALUES (%s, %s)", (cost_id, p))
    return split_of(conn, trip_id)


@router.put("/travel/expenses/{expense_id}/split")
def split_expense(expense_id: int, body: SplitIn):
    with db() as conn:
        return set_split(conn, "expense", expense_id, body)


@router.put("/travel/bookings/{booking_id}/split")
def split_booking(booking_id: int, body: SplitIn):
    with db() as conn:
        return set_split(conn, "booking", booking_id, body)


# ---------------------------------------------------------------------------------------------
# The day-by-day map
# ---------------------------------------------------------------------------------------------
@router.get("/travel/trips/{trip_id}/day-map")
def day_map(trip_id: int):
    """Each day's stops in order: the day plan's items that have a place with a position (by time), then places that
    just say which day you visit them. Between stops: the straight-line distance and a rough road / time estimate."""
    with db() as conn:
        t = trip_row(conn, trip_id)
        planned = conn.execute("""
            SELECT i.day, i.at, i.title, p.place_id, p.name, p.lat::float8 AS lat, p.lon::float8 AS lon, i.item_id
            FROM trip_plan i JOIN trip_places p ON p.place_id = i.place_id
            WHERE i.trip_id = %s AND i.day IS NOT NULL ORDER BY i.day, i.at NULLS LAST, i.item_id""", (trip_id,)).fetchall()
        visits = conn.execute("""
            SELECT p.visit_on AS day, NULL::time AS at, p.name AS title, p.place_id, p.name, p.lat::float8 AS lat, p.lon::float8 AS lon
            FROM trip_places p WHERE p.trip_id = %s AND p.visit_on IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM trip_plan i WHERE i.trip_id = p.trip_id AND i.place_id = p.place_id AND i.day = p.visit_on)
            ORDER BY p.visit_on, p.stop_order NULLS LAST, p.place_id""", (trip_id,)).fetchall()
        no_day = conn.execute("SELECT count(*)::int AS n FROM trip_plan i LEFT JOIN trip_places p ON p.place_id = i.place_id "
                              "WHERE i.trip_id = %s AND i.day IS NOT NULL AND (p.place_id IS NULL OR p.lat IS NULL)", (trip_id,)).fetchone()["n"]
    by_day: dict[date, list[dict]] = {}
    for s in [*planned, *visits]:
        if s["lat"] is None or s["lon"] is None:
            continue
        by_day.setdefault(s["day"], []).append({k: s[k] for k in ("title", "place_id", "name", "lat", "lon", "at")})
    days = []
    for n, (day, stops) in enumerate(sorted(by_day.items()), 1):
        legs = [leg(a, b) for a, b in zip(stops, stops[1:]) if (a["lat"], a["lon"]) != (b["lat"], b["lon"])]
        start = t["start_date"]
        days.append({"day": day, "number": (day - start).days + 1 if start else n, "stops": stops, "legs": legs,
                     "km": round(sum(x["km"] for x in legs), 1), "road_km": round(sum(x["road_km"] for x in legs), 1),
                     "drive_min": sum(x["drive_min"] for x in legs)})
    return {"trip_id": trip_id, "days": days, "without_position": no_day,
            "note": "Distances are straight lines; the road and time figures are rough estimates (no routing service is asked)."}
