"""Travel: what's on a trip (77_travel.sql) - every change answers with the whole trip (travel.trip_detail).

    POST /travel/trips/{id}/bookings, PATCH / DELETE /travel/bookings/{id}   flights, stays, cars, tours...
    POST /travel/trips/{id}/plan, PATCH / DELETE /travel/plan/{id}           the day plan (no day = before you go)
    POST /travel/trips/{id}/expenses, PATCH / DELETE /travel/expenses/{id}   money spent there
    PUT  /travel/trips/{id}/rates/{currency}                                 your own rate for a currency (or none)
    GET  /travel/rates                                                       today's rates (Frankfurter, the ECB's)
    POST /travel/trips/{id}/packing (+ /from-list, /gear, /unpack), PATCH / DELETE /travel/packing/{id}
    GET / POST /travel/packing-lists, PATCH / DELETE /travel/packing-lists/{id}   reusable lists
    PUT  /travel/trips/{id}/entries/{day}                                    the journal: that day's note
    POST /travel/trips/{id}/photos, GET / PATCH / DELETE /travel/photos/{id}

Money in another currency is kept as it was (amount + currency) with the rate to AUD when it was entered: your own
rate for that currency on the trip if you've set one, else the day's published rate (Frankfurter). A booking or
expense keeps its rate unless you change its currency or give a new one.
"""
from datetime import date, datetime, time

from fastapi import APIRouter, HTTPException, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import frankfurter
from .db import db, found, insert_row, tidy_text, update_row
from .images import photo_response, read_photo
from .travel import BOOKING_KINDS, CATEGORIES, GROUPS, HOBBIES, PHOTO_SELECT, _lit, trip_detail, trip_row

router = APIRouter(prefix="/api", tags=["travel"])


def _trip_of(conn, table: str, id_col: str, row_id: int, what: str) -> int:
    return found(conn.execute(f"SELECT trip_id FROM {table} WHERE {id_col} = %s", (row_id,)).fetchone(), what)["trip_id"]


def _required(data: dict, *names):
    for name in names:
        if name in data and data[name] is None:
            raise HTTPException(422, f"{name.replace('_', ' ').capitalize()} can't be empty.")


# ---------------------------------------------------------------------------------------------
# Money: rates
# ---------------------------------------------------------------------------------------------
def rate_for(conn, trip_id: int, currency: str) -> float:
    """AUD for one unit of the currency: 1 for AUD; your rate on the trip; else today's published one."""
    if currency == "AUD":
        return 1.0
    mine = (conn.execute("SELECT rates FROM trips WHERE trip_id = %s", (trip_id,)).fetchone()["rates"] or {}).get(currency)
    if mine:
        return float(mine)
    try:
        rate = frankfurter.aud_per(currency)
    except frankfurter.RatesError as e:
        raise HTTPException(422, f"{e} Set your own {currency} rate for this trip (Money â†’ Rates).") from None
    if rate is None:
        raise HTTPException(422, f"There's no published rate for {currency} - set your own for this trip (Money â†’ Rates).")
    return rate


def _money(conn, trip_id: int, data: dict, old: dict | None = None):
    """The rate: as given; else looked up for a new row or a changed currency; else unchanged."""
    if "currency" in data:
        data["currency"] = (data["currency"] or "AUD").upper()
    if data.get("rate") is not None:
        return
    data.pop("rate", None)
    currency = data.get("currency", old["currency"] if old else "AUD")
    if old is None or currency != old["currency"]:
        data["rate"] = rate_for(conn, trip_id, currency)


class RateIn(BaseModel):
    rate: float | None = Field(None, gt=0, le=100000)


@router.put("/travel/trips/{trip_id}/rates/{currency}")
def set_rate(trip_id: int, currency: str, body: RateIn, apply: bool = False):
    """Your rate for a currency on this trip (AUD for one unit), or none to use the published one again.
    apply=true also re-prices the trip's bookings and expenses in that currency."""
    currency = currency.upper()
    if len(currency) != 3 or not currency.isalpha() or currency == "AUD":
        raise HTTPException(422, "A currency is a three-letter code other than AUD (JPY, USD).")
    with db() as conn:
        trip_row(conn, trip_id)
        if body.rate is None:
            conn.execute("UPDATE trips SET rates = rates - %s WHERE trip_id = %s", (currency, trip_id))
        else:
            conn.execute("UPDATE trips SET rates = rates || %s WHERE trip_id = %s", (Jsonb({currency: body.rate}), trip_id))
        if apply:
            rate = rate_for(conn, trip_id, currency)
            for table in ("trip_bookings", "trip_expenses"):
                conn.execute(f"UPDATE {table} SET rate = %s WHERE trip_id = %s AND currency = %s", (rate, trip_id, currency))
        return trip_detail(conn, trip_id)


@router.get("/travel/rates")
def rates():
    try:
        return frankfurter.rates()
    except frankfurter.RatesError as e:
        raise HTTPException(502, str(e)) from None


# ---------------------------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------------------------
class BookingFields(BaseModel):
    kind: str | None = Field(None, pattern=_lit(BOOKING_KINDS))
    provider: str | None = Field(None, max_length=200)
    reference: str | None = Field(None, max_length=120)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    from_place: str | None = Field(None, max_length=200)
    to_place: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    cost: float | None = Field(None, ge=0, le=10_000_000)
    currency: str | None = Field(None, pattern="^[A-Za-z]{3}$")
    rate: float | None = Field(None, gt=0, le=100000)
    paid: bool | None = None
    link: str | None = Field(None, max_length=1000, pattern="^https?://")
    notes: str | None = Field(None, max_length=5000)


class BookingIn(BookingFields):
    kind: str = Field(pattern=_lit(BOOKING_KINDS))
    title: str = Field(min_length=1, max_length=200)


class BookingPatch(BookingFields):
    title: str | None = Field(None, min_length=1, max_length=200)


def _naive(data: dict):
    """Times are local to where they happen: keep what was typed, drop any zone."""
    for k in ("starts_at", "ends_at"):
        if isinstance(data.get(k), datetime) and data[k].tzinfo is not None:
            data[k] = data[k].replace(tzinfo=None)
    if data.get("starts_at") and data.get("ends_at") and data["ends_at"] < data["starts_at"]:
        raise HTTPException(422, "It has to end after it starts.")


@router.post("/travel/trips/{trip_id}/bookings", status_code=201)
def add_booking(trip_id: int, body: BookingIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("title",))
    _naive(data)
    with db() as conn:
        trip_row(conn, trip_id)
        _money(conn, trip_id, data)
        insert_row(conn, "trip_bookings", {**data, "trip_id": trip_id}, "booking_id")
        return trip_detail(conn, trip_id)


@router.patch("/travel/bookings/{booking_id}")
def update_booking(booking_id: int, body: BookingPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    _required(data, "title", "kind", "paid")
    _naive(data)
    with db() as conn:
        old = found(conn.execute("SELECT * FROM trip_bookings WHERE booking_id = %s", (booking_id,)).fetchone(), "Booking")
        if data.get("starts_at", old["starts_at"]) and data.get("ends_at", old["ends_at"]) \
                and data.get("ends_at", old["ends_at"]) < data.get("starts_at", old["starts_at"]):
            raise HTTPException(422, "It has to end after it starts.")
        _money(conn, old["trip_id"], data, old)
        update_row(conn, "trip_bookings", "booking_id", booking_id, data)
        return trip_detail(conn, old["trip_id"])


@router.delete("/travel/bookings/{booking_id}")
def delete_booking(booking_id: int):
    with db() as conn:
        trip_id = _trip_of(conn, "trip_bookings", "booking_id", booking_id, "Booking")
        conn.execute("DELETE FROM trip_bookings WHERE booking_id = %s", (booking_id,))
        return trip_detail(conn, trip_id)


# ---------------------------------------------------------------------------------------------
# The day plan
# ---------------------------------------------------------------------------------------------
class PlanFields(BaseModel):
    day: date | None = None
    at: time | None = None
    place_id: int | None = None
    notes: str | None = Field(None, max_length=5000)
    done: bool | None = None


class PlanIn(PlanFields):
    title: str = Field(min_length=1, max_length=300)


class PlanPatch(PlanFields):
    title: str | None = Field(None, min_length=1, max_length=300)


def _place_on(conn, trip_id: int, place_id: int | None):
    if place_id is not None and not conn.execute("SELECT 1 FROM trip_places WHERE place_id = %s AND trip_id = %s",
                                                 (place_id, trip_id)).fetchone():
        raise HTTPException(422, "That place isn't on this trip.")


@router.post("/travel/trips/{trip_id}/plan", status_code=201)
def add_plan(trip_id: int, body: PlanIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("title",))
    with db() as conn:
        trip_row(conn, trip_id)
        _place_on(conn, trip_id, data.get("place_id"))
        insert_row(conn, "trip_plan", {**data, "trip_id": trip_id}, "item_id")
        return trip_detail(conn, trip_id)


@router.patch("/travel/plan/{item_id}")
def update_plan(item_id: int, body: PlanPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    _required(data, "title", "done")
    with db() as conn:
        trip_id = _trip_of(conn, "trip_plan", "item_id", item_id, "Plan item")
        _place_on(conn, trip_id, data.get("place_id"))
        update_row(conn, "trip_plan", "item_id", item_id, data)
        return trip_detail(conn, trip_id)


@router.delete("/travel/plan/{item_id}")
def delete_plan(item_id: int):
    with db() as conn:
        trip_id = _trip_of(conn, "trip_plan", "item_id", item_id, "Plan item")
        conn.execute("DELETE FROM trip_plan WHERE item_id = %s", (item_id,))
        return trip_detail(conn, trip_id)


# ---------------------------------------------------------------------------------------------
# Money spent there
# ---------------------------------------------------------------------------------------------
class ExpenseFields(BaseModel):
    spent_on: date | None = None
    category: str | None = Field(None, pattern=_lit(CATEGORIES))
    what: str | None = Field(None, max_length=300)
    currency: str | None = Field(None, pattern="^[A-Za-z]{3}$")
    rate: float | None = Field(None, gt=0, le=100000)


class ExpenseIn(ExpenseFields):
    amount: float = Field(ge=0, le=10_000_000)


class ExpensePatch(ExpenseFields):
    amount: float | None = Field(None, ge=0, le=10_000_000)


@router.post("/travel/trips/{trip_id}/expenses", status_code=201)
def add_expense(trip_id: int, body: ExpenseIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
    with db() as conn:
        trip_row(conn, trip_id)
        _money(conn, trip_id, data)
        insert_row(conn, "trip_expenses", {**data, "trip_id": trip_id}, "expense_id")
        return trip_detail(conn, trip_id)


@router.patch("/travel/expenses/{expense_id}")
def update_expense(expense_id: int, body: ExpensePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    _required(data, "amount", "spent_on", "category")
    with db() as conn:
        old = found(conn.execute("SELECT * FROM trip_expenses WHERE expense_id = %s", (expense_id,)).fetchone(), "Expense")
        _money(conn, old["trip_id"], data, old)
        update_row(conn, "trip_expenses", "expense_id", expense_id, data)
        return trip_detail(conn, old["trip_id"])


@router.delete("/travel/expenses/{expense_id}")
def delete_expense(expense_id: int):
    with db() as conn:
        trip_id = _trip_of(conn, "trip_expenses", "expense_id", expense_id, "Expense")
        conn.execute("DELETE FROM trip_expenses WHERE expense_id = %s", (expense_id,))
        return trip_detail(conn, trip_id)


# ---------------------------------------------------------------------------------------------
# Packing
# ---------------------------------------------------------------------------------------------
class PackIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    grp: str = Field("Other", pattern=_lit(GROUPS))
    qty: int = Field(1, ge=1, le=999)


class PackPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    grp: str | None = Field(None, pattern=_lit(GROUPS))
    qty: int | None = Field(None, ge=1, le=999)
    packed: bool | None = None


def _pack(conn, trip_id: int, name: str, grp: str, qty: int = 1, gear_id: int | None = None) -> bool:
    """Add one thing to pack, unless it's on the list already (by name). True if it was added."""
    return conn.execute("INSERT INTO trip_packing (trip_id, name, grp, qty, gear_id) VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (trip_id, name) DO NOTHING RETURNING item_id",
                        (trip_id, name.strip(), grp, qty, gear_id)).fetchone() is not None


@router.post("/travel/trips/{trip_id}/packing", status_code=201)
def add_packing(trip_id: int, body: PackIn):
    with db() as conn:
        trip_row(conn, trip_id)
        if not body.name.strip():
            raise HTTPException(422, "What is it?")
        if not _pack(conn, trip_id, body.name, body.grp, body.qty):
            raise HTTPException(409, f"{body.name.strip()} is on the list already.")
        return trip_detail(conn, trip_id)


class FromListIn(BaseModel):
    list_id: int


@router.post("/travel/trips/{trip_id}/packing/from-list")
def pack_from_list(trip_id: int, body: FromListIn):
    """Everything on a packing list that isn't on the trip's list yet."""
    with db() as conn:
        trip_row(conn, trip_id)
        items = found(conn.execute("SELECT items FROM packing_lists WHERE list_id = %s", (body.list_id,)).fetchone(),
                      "Packing list")["items"]
        for i in items:
            _pack(conn, trip_id, i["name"], i.get("grp") if i.get("grp") in GROUPS else "Other", i.get("qty") or 1)
        return trip_detail(conn, trip_id)


class GearIn(BaseModel):
    hobby: str = Field(pattern=_lit(HOBBIES))


@router.post("/travel/trips/{trip_id}/packing/gear")
def pack_gear(trip_id: int, body: GearIn):
    """Your gear for a hobby (not retired) - your hiking boots, knee pads, range bag - onto the list."""
    with db() as conn:
        trip_row(conn, trip_id)
        gear = conn.execute("SELECT gear_id, name FROM gear WHERE hobby = %s AND condition <> 'Retired' ORDER BY lower(name)",
                            (body.hobby,)).fetchall()
        if not gear:
            raise HTTPException(422, "You haven't any gear for that hobby yet.")
        for g in gear:
            _pack(conn, trip_id, g["name"], "Gear", 1, g["gear_id"])
        return trip_detail(conn, trip_id)


@router.post("/travel/trips/{trip_id}/packing/unpack")
def unpack_all(trip_id: int):
    """Untick everything (to pack for the trip home)."""
    with db() as conn:
        trip_row(conn, trip_id)
        conn.execute("UPDATE trip_packing SET packed = false WHERE trip_id = %s", (trip_id,))
        return trip_detail(conn, trip_id)


@router.patch("/travel/packing/{item_id}")
def update_packing(item_id: int, body: PackPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    _required(data, "name", "grp", "qty", "packed")
    with db() as conn:
        trip_id = _trip_of(conn, "trip_packing", "item_id", item_id, "Packing item")
        if "name" in data and conn.execute("SELECT 1 FROM trip_packing WHERE trip_id = %s AND name = %s AND item_id <> %s",
                                           (trip_id, data["name"], item_id)).fetchone():
            raise HTTPException(409, f"{data['name']} is on the list already.")
        update_row(conn, "trip_packing", "item_id", item_id, data)
        return trip_detail(conn, trip_id)


@router.delete("/travel/packing/{item_id}")
def delete_packing(item_id: int):
    with db() as conn:
        trip_id = _trip_of(conn, "trip_packing", "item_id", item_id, "Packing item")
        conn.execute("DELETE FROM trip_packing WHERE item_id = %s", (item_id,))
        return trip_detail(conn, trip_id)


# Reusable lists
class ListItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    grp: str = Field("Other", pattern=_lit(GROUPS))
    qty: int | None = Field(None, ge=1, le=999)


class ListIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    items: list[ListItem] | None = Field(None, max_length=300)
    from_trip: int | None = None          # or: everything on this trip's list


class ListPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    items: list[ListItem] | None = Field(None, max_length=300)


def _items(items: list[ListItem]) -> Jsonb:
    seen, out = set(), []
    for i in items:
        name = i.name.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name, "grp": i.grp, **({"qty": i.qty} if i.qty and i.qty > 1 else {})})
    return Jsonb(out)


def packing_lists(conn):
    return conn.execute("SELECT list_id, name, items, jsonb_array_length(items) AS count FROM packing_lists "
                        "ORDER BY lower(name)").fetchall()


@router.get("/travel/packing-lists")
def list_packing_lists():
    with db() as conn:
        return packing_lists(conn)


def _name_free(conn, name: str, list_id: int | None = None):
    if conn.execute("SELECT 1 FROM packing_lists WHERE lower(name) = lower(%s) AND list_id IS DISTINCT FROM %s",
                    (name, list_id)).fetchone():
        raise HTTPException(409, f"There's a list called {name} already.")


@router.post("/travel/packing-lists", status_code=201)
def add_packing_list(body: ListIn):
    name = body.name.strip()
    with db() as conn:
        _name_free(conn, name)
        if body.from_trip is not None:
            trip_row(conn, body.from_trip)
            rows = conn.execute("SELECT name, grp, qty FROM trip_packing WHERE trip_id = %s AND gear_id IS NULL ORDER BY item_id",
                                (body.from_trip,)).fetchall()
            items = [ListItem(**r) for r in rows]
        else:
            items = body.items or []
        conn.execute("INSERT INTO packing_lists (name, items) VALUES (%s, %s)", (name, _items(items)))
        return packing_lists(conn)


@router.patch("/travel/packing-lists/{list_id}")
def update_packing_list(list_id: int, body: ListPatch):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM packing_lists WHERE list_id = %s", (list_id,)).fetchone(), "Packing list")
        if body.name is not None:
            _name_free(conn, body.name.strip(), list_id)
            conn.execute("UPDATE packing_lists SET name = %s WHERE list_id = %s", (body.name.strip(), list_id))
        if body.items is not None:
            conn.execute("UPDATE packing_lists SET items = %s WHERE list_id = %s", (_items(body.items), list_id))
        return packing_lists(conn)


@router.delete("/travel/packing-lists/{list_id}")
def delete_packing_list(list_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM packing_lists WHERE list_id = %s RETURNING list_id", (list_id,)).fetchone(), "Packing list")
        return packing_lists(conn)


# ---------------------------------------------------------------------------------------------
# The journal and photos
# ---------------------------------------------------------------------------------------------
class EntryIn(BaseModel):
    text: str = Field("", max_length=50000)


@router.put("/travel/trips/{trip_id}/entries/{day}")
def put_entry(trip_id: int, day: date, body: EntryIn):
    """That day's note (empty = none)."""
    with db() as conn:
        trip_row(conn, trip_id)
        if body.text.strip():
            conn.execute("""INSERT INTO trip_entries (trip_id, day, text) VALUES (%s, %s, %s)
                            ON CONFLICT (trip_id, day) DO UPDATE SET text = EXCLUDED.text, updated_at = now()""",
                         (trip_id, day, body.text.strip()))
        else:
            conn.execute("DELETE FROM trip_entries WHERE trip_id = %s AND day = %s", (trip_id, day))
        return trip_detail(conn, trip_id)


@router.post("/travel/trips/{trip_id}/photos", status_code=201)
async def add_photo(trip_id: int, request: Request, lat: float | None = None, lon: float | None = None,
                    taken: str | None = None, day: date | None = None, caption: str | None = None):
    """A photo (the body, shrunk by the browser). lat / lon / taken come from its EXIF; its day is the day it was
    taken (or the one given)."""
    image, image_type = await read_photo(request)
    taken_at = None
    if taken:
        try:
            taken_at = datetime.fromisoformat(taken)
        except ValueError:
            raise HTTPException(422, "The photo's time isn't a date and time.") from None
    if lat is not None and not (-90 <= lat <= 90 and -180 <= (lon or 0) <= 180 and lon is not None):
        lat = lon = None
    with db() as conn:
        trip_row(conn, trip_id)
        insert_row(conn, "trip_photos", {"trip_id": trip_id, "image": image, "image_type": image_type, "lat": lat, "lon": lon,
                                         "taken_at": taken_at, "day": day or (taken_at.date() if taken_at else None),
                                         "caption": (caption or "").strip() or None}, "photo_id")
        return trip_detail(conn, trip_id)


@router.get("/travel/photos/{photo_id}")
def get_photo(photo_id: int):
    """A photo never changes (a new one gets a new id), so it's cached for a year."""
    with db() as conn:
        row = found(conn.execute("SELECT image, image_type FROM trip_photos WHERE photo_id = %s", (photo_id,)).fetchone(), "Photo")
    return photo_response(row["image"], row["image_type"])


class PhotoPatch(BaseModel):
    caption: str | None = Field(None, max_length=1000)
    day: date | None = None


@router.patch("/travel/photos/{photo_id}")
def update_photo(photo_id: int, body: PhotoPatch):
    data = body.model_dump(exclude_unset=True)
    if "caption" in data:
        data["caption"] = (data["caption"] or "").strip() or None
    with db() as conn:
        trip_id = _trip_of(conn, "trip_photos", "photo_id", photo_id, "Photo")
        update_row(conn, "trip_photos", "photo_id", photo_id, data)
        return trip_detail(conn, trip_id)


@router.delete("/travel/photos/{photo_id}")
def delete_photo(photo_id: int):
    with db() as conn:
        trip_id = _trip_of(conn, "trip_photos", "photo_id", photo_id, "Photo")
        conn.execute("DELETE FROM trip_photos WHERE photo_id = %s", (photo_id,))
        return trip_detail(conn, trip_id)


@router.get("/travel/photos")
def all_photos():
    """Every trip photo with a place on the map (for the Places map)."""
    with db() as conn:
        return conn.execute(PHOTO_SELECT + " WHERE lat IS NOT NULL ORDER BY taken_at NULLS LAST, photo_id").fetchall()
