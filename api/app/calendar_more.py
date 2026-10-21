"""More for the calendar (2026-10-21, from a scan of Google / Apple Calendar, Fantastical, Notion Calendar, Sunsama):

    parse       quick add in plain words: "Volleyball Tue 7-9pm at Sports hall weekly" -> the event's fields
    search      events by words in their title, place or notes (with when they're next on)
    countdowns  events you count down to ("Regional comp in 12 days")
    weather     the forecast on events in the next 16 days (their place, else where you live) - Open-Meteo
    balance     per hobby: time planned (events with times) and done (each hobby's own log, where it keeps time)
    year        a year, day by day: how much you did and how it felt
    bring       what an event's checklist can take in: the hobby's gear (rifles and ammo for shooting) and packing lists
    move        drag an event to another day / time (one day of a repeating event: that day only)
"""
import calendar as months
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from . import activity, openmeteo, vgplaytime
from .calendar import MAX_DAYS, days_of, fetch_event, occurrences
from .db import MODULE_IDS, db, insert_row, update_row
from .holidays import holidays_between

router = APIRouter(prefix="/api", tags=["calendar"])

# What each hobby's log shows as in the activity feed (activity.py kinds): a hobby event that day counts as done.
HOBBY_KINDS = {"models": ("model",), "boardgames": ("game",), "volleyball": ("volleyball",), "videogames": ("videogame",),
               "chess": ("chess",), "reading": ("book",), "travel": ("trip",), "shooting": ("shoot",), "hiking": ("hike",),
               "gardening": ("planting", "gcontainer", "gspace"), "car": ()}
KIND_HOBBY = {k: h for h, kinds in HOBBY_KINDS.items() for k in kinds}


def today(conn) -> date:
    return conn.execute("SELECT current_date AS d").fetchone()["d"]      # Brisbane


# ---------------------------------------------------------------- quick add
WEEKDAYS = [("monday", "mon"), ("tuesday", "tue", "tues"), ("wednesday", "wed"), ("thursday", "thu", "thur", "thurs"),
            ("friday", "fri"), ("saturday", "sat"), ("sunday", "sun")]
DAY_WORD = {w: i for i, names in enumerate(WEEKDAYS) for w in names}
DAY_RE = "|".join(sorted(DAY_WORD, key=len, reverse=True))
MONTH_WORD = {m.lower(): i for i, m in enumerate(months.month_name) if m} | \
    {m.lower(): i for i, m in enumerate(months.month_abbr) if m} | {"sept": 9}
MONTH_RE = "|".join(sorted(MONTH_WORD, key=len, reverse=True))
NTH = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "last": 5}
HOBBY_WORDS = [  # (pattern, hobby) - the first that matches wins
    (r"volley ?ball|vball", "volleyball"), (r"chess", "chess"),
    (r"shoot(?:ing)?|range day|rifle|rimfire|club match|prs", "shooting"),
    (r"hike|hiking|bushwalk|trail|summit", "hiking"), (r"garden(?:ing)?|repot|sow(?:ing)?|plant(?:ing)? out", "gardening"),
    (r"board ?games?|games? night|catan|wingspan|d&d|dnd", "boardgames"), (r"book club|reading|library", "reading"),
    (r"model|airbrush|warhammer|gundam|paint(?:ing)? night|kit build|hobby show", "models"),
    (r"gaming|video ?games?|steam|xbox|playstation|ps5|lan party", "videogames"),
    (r"flight|trip|travel|airport", "travel"), (r"track day|mechanic|car meet", "car"),
]


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


def _hour(h: int, m: int, ampm: str | None, guess_pm: bool) -> time | None:
    if ampm == "pm" and h < 12:
        h += 12
    elif ampm == "am" and h == 12:
        h = 0
    elif ampm is None and guess_pm and 1 <= h <= 7:     # "at 7": a hobby's evening, not 7 in the morning
        h += 12
    return time(h, m) if 0 <= h <= 23 and 0 <= m <= 59 else None


def _next_weekday(now: date, wd: int, strictly_after: bool = False) -> date:
    ahead = (wd - now.weekday()) % 7
    return now + timedelta(days=ahead if ahead or not strictly_after else 7)


def _nth_weekday(year: int, month: int, wd: int, nth: int) -> date:
    first = date(year, month, 1)
    d = first + timedelta(days=(wd - first.weekday()) % 7)
    if nth == 5:
        while (d + timedelta(days=7)).month == month:
            d += timedelta(days=7)
        return d
    return d + timedelta(days=7 * (nth - 1))


def parse(text: str, now: date) -> dict:
    """Plain words -> an event's fields, and what was understood (to show before adding)."""
    s = " " + " ".join(text.split()) + " "
    low = s.lower()
    out = {"title": "", "hobby": None, "starts_on": now, "start_time": None, "end_time": None, "location": None,
           "repeats": "never", "repeat_every": 1, "repeat_days": None, "repeat_until": None}
    spans = []                                              # what was read as when / where: cut from the title

    def take(m, group=0):
        spans.append(m.span(group))

    day_set = False
    # repeats
    m = re.search(rf"\bon the (first|1st|second|2nd|third|3rd|fourth|4th|last) ({DAY_RE})\w* (?:of )?(?:the |each |every )?month\b", low)
    if m:
        take(m)
        wd, nth = DAY_WORD[m.group(2)], NTH[m.group(1)]
        d = _nth_weekday(now.year, now.month, wd, nth)
        if d < now:
            nm = date(now.year + (now.month == 12), now.month % 12 + 1, 1)
            d = _nth_weekday(nm.year, nm.month, wd, nth)
        out.update(repeats="monthly_nth", starts_on=d)
        day_set = True
    m = re.search(rf"\bevery ((?:{DAY_RE})\w*(?:(?:\s*,\s*|\s+and\s+|\s*&\s*)(?:{DAY_RE})\w*)*)\b", low)
    if m and not day_set:
        take(m)
        days = sorted({DAY_WORD[w] for w in re.findall(DAY_RE, m.group(1)) if w in DAY_WORD})
        if len(days) == 1:
            out.update(repeats="weekly", starts_on=_next_weekday(now, days[0]))
        else:
            out.update(repeats="weekdays", repeat_days=days, starts_on=min(_next_weekday(now, d) for d in days))
        day_set = True
    for pattern, kind, every in ((r"\bevery other week\b|\bevery second week\b|\bfortnightly\b|\bevery fortnight\b", "fortnightly", 1),
                                 (r"\bevery (\d{1,2}) weeks\b", "weekly", None), (r"\bweekly\b|\bevery week\b", "weekly", 1),
                                 (r"\bmonthly\b|\bevery month\b", "monthly", 1), (r"\byearly\b|\bannually\b|\bevery year\b", "yearly", 1)):
        m = re.search(pattern, low)
        if m:
            take(m)
            if out["repeats"] == "never" or kind == "weekly" and every is None:
                out["repeats"] = kind
            if every is None:
                out["repeat_every"] = max(1, min(12, int(m.group(1))))
            break
    # until (for a repeating event)
    m = re.search(rf"\buntil (\d{{1,2}})(?:st|nd|rd|th)? ({MONTH_RE})\b|\buntil ({MONTH_RE}) (\d{{1,2}})\b|\buntil ({MONTH_RE})\b", low)
    if m and out["repeats"] != "never":
        take(m)
        mon = MONTH_WORD[m.group(2) or m.group(3) or m.group(5)]
        dd = int(m.group(1) or m.group(4) or 0)
        year = now.year + (mon < now.month)
        try:
            out["repeat_until"] = date(year, mon, dd) if dd else date(year, mon, months.monthrange(year, mon)[1])
        except ValueError:                                   # "until 31 Feb": no such day - just no end
            pass
    # times: a range first ("7-9pm", "from 6:30 to 8"), then one time ("at 7pm", "19:00", "noon")
    tm = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
    m = re.search(rf"(?:\bfrom\s+|\bat\s+|@\s*)?\b{tm}\s*(?:-|–|to|until|till)\s*{tm}(?=\W)", low)
    if m and (m.group(3) or m.group(6) or m.group(2) or m.group(5)):
        take(m)
        end_ampm = m.group(6)
        end = _hour(int(m.group(4)), int(m.group(5) or 0), end_ampm, True)
        start = _hour(int(m.group(1)), int(m.group(2) or 0), m.group(3), False)
        if start and end and not m.group(3) and end_ampm == "pm" and start.hour + 12 < end.hour + (end.minute > 0):
            start = time(start.hour + 12, start.minute)
        if start and end and start > end and not m.group(3) and start.hour < 12:
            start = time(start.hour + 12, start.minute) if start.hour + 12 < 24 else start
        out.update(start_time=start, end_time=end)
    else:
        m = re.search(r"(?:\bat\s+|@\s*)?\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|(?:\bat\s+|@\s*)?\b(\d{1,2}):(\d{2})\b|"
                      r"\bat (\d{1,2})\b(?!\s*(?:" + MONTH_RE + r"|/|-))|\b(noon|midday)\b", low)
        if m:
            take(m)
            if m.group(7):
                out["start_time"] = time(12, 0)
            elif m.group(1):
                out["start_time"] = _hour(int(m.group(1)), int(m.group(2) or 0), m.group(3), False)
            elif m.group(4):
                out["start_time"] = _hour(int(m.group(4)), int(m.group(5)), None, False)
            else:
                out["start_time"] = _hour(int(m.group(6)), 0, None, True)
    m = re.search(r"\bfor (\d{1,3}(?:\.\d)?) ?(hours?|hrs?|h|minutes?|mins?|m)\b", low)
    if m and out["start_time"]:
        take(m)
        mins = float(m.group(1)) * (60 if m.group(2).startswith("h") else 1)
        end = datetime.combine(now, out["start_time"]) + timedelta(minutes=mins)
        if end.date() == now:
            out["end_time"] = end.time()
    # the day
    if not day_set:
        for pattern, fn in (
            (r"\bday after tomorrow\b", lambda m: now + timedelta(days=2)),
            (r"\btomorrow\b|\btmrw\b", lambda m: now + timedelta(days=1)),
            (r"\btoday\b|\btonight\b", lambda m: now),
            (r"\bin (\d{1,3}) days?\b", lambda m: now + timedelta(days=int(m.group(1)))),
            (r"\bin (\d{1,2}) weeks?\b", lambda m: now + timedelta(weeks=int(m.group(1)))),
            # (a weekday beside a date goes with it: "Sat 28 Nov")
            (rf"\b(?:(?:{DAY_RE})\w*,? )?(?:on )?(?:the )?(\d{{1,2}})(?:st|nd|rd|th)? (?:of )?({MONTH_RE})\b(?: (\d{{4}}))?",
             lambda m: _dated(now, int(m.group(1)), MONTH_WORD[m.group(2)], m.group(3))),
            (rf"\b(?:(?:{DAY_RE})\w*,? )?(?:on )?({MONTH_RE}) (\d{{1,2}})(?:st|nd|rd|th)?\b(?: (\d{{4}}))?",
             lambda m: _dated(now, int(m.group(2)), MONTH_WORD[m.group(1)], m.group(3))),
            (r"\b(?:on )?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", lambda m: _dated(now, int(m.group(1)), int(m.group(2)), m.group(3))),
            (rf"\bnext ({DAY_RE})\w*\b", lambda m: _next_weekday(now, DAY_WORD[m.group(1)], True)),
            (rf"\b(?:on |this )?({DAY_RE})(?:day|nesday|rsday|sday|urday|s)?\b", lambda m: _next_weekday(now, DAY_WORD[m.group(1)])),
        ):
            m = re.search(pattern, low)
            if m:
                d = fn(m)
                if d:
                    take(m)
                    out["starts_on"] = d
                    break
    # where: "at <a place>" (not a time), up to a comma or the end
    m = re.search(r"\b(?:at|@) (?!\d)([^,]+?)\s*(?=,|$)", _blank(low, spans))
    if m:
        take(m)
        out["location"] = s[m.start(1):m.end(1)].strip(" .") or None
    # what: whatever's left
    title = _blank(s, spans)
    title = re.sub(r"\s+(?:on|at|from|every|the|and)\s*$", "", " ".join(title.split()), flags=re.I).strip(" ,.-")
    title = re.sub(r"^(?:on|at|from)\s+", "", title, flags=re.I)
    out["title"] = (title[:1].upper() + title[1:]) if title else "Event"
    for pattern, hobby in HOBBY_WORDS:
        if hobby in MODULE_IDS and re.search(rf"\b(?:{pattern})\b", low):
            out["hobby"] = hobby
            break
    return out


def _dated(now: date, day: int, month: int, year: str | None) -> date | None:
    """A day and month (and maybe a year); without a year, the next time it comes round."""
    try:
        y = int(year) + (2000 if year and len(year) == 2 else 0) if year else now.year
        d = date(y, month, day)
        return d if year or d >= now else date(y + 1, month, day)
    except ValueError:
        return None


def _blank(s: str, spans: list[tuple[int, int]]) -> str:
    out = list(s)
    for a, b in spans:
        out[a:b] = " " * (b - a)
    return "".join(out)


@router.post("/calendar/parse")
def parse_text(body: ParseIn):
    """Quick add: what the words say, to check before adding (the event isn't made here)."""
    with db() as conn:
        return parse(body.text, today(conn))


# ---------------------------------------------------------------- search, countdowns
def next_day(event: dict, start: date, days: int = MAX_DAYS) -> date | None:
    on = days_of(event, start, start + timedelta(days=days))
    return on[0] if on else None


@router.get("/calendar/search")
def search(q: str = Query(..., min_length=1, max_length=100)):
    """Events with every word somewhere in their title, place or notes; with the next day each is on (or its last)."""
    words = q.split()
    where = " AND ".join(["(title ILIKE %s OR location ILIKE %s OR notes ILIKE %s)"] * len(words))
    with db() as conn:
        now = today(conn)
        rows = conn.execute(f"SELECT * FROM calendar_events WHERE {where} ORDER BY starts_on DESC LIMIT 50",
                            [f"%{w}%" for w in words for _ in range(3)]).fetchall()
    out = []
    for e in rows:
        nxt = next_day(e, now)
        past = days_of(e, max(e["starts_on"], now - timedelta(days=MAX_DAYS)), now - timedelta(days=1)) if not nxt else []
        out.append({"event_id": e["event_id"], "title": e["title"], "hobby": e["hobby"], "location": e["location"],
                    "start_time": e["start_time"], "repeats": e["repeats"], "day": nxt or (past[-1] if past else e["starts_on"]),
                    "upcoming": nxt is not None})
    return sorted(out, key=lambda e: (not e["upcoming"], e["day"] if e["upcoming"] else date.max - e["day"]))


@router.get("/calendar/countdowns")
def countdowns():
    """Events marked to count down to, soonest first, with the days left."""
    with db() as conn:
        now = today(conn)
        rows = conn.execute("SELECT * FROM calendar_events WHERE countdown").fetchall()
    out = []
    for e in rows:
        nxt = next_day(e, now)
        if nxt:
            out.append({"event_id": e["event_id"], "title": e["title"], "hobby": e["hobby"], "day": nxt,
                        "start_time": e["start_time"], "location": e["location"], "days_left": (nxt - now).days})
    return sorted(out, key=lambda e: e["day"])


# ---------------------------------------------------------------- weather
def home(conn) -> dict | None:
    s = conn.execute("SELECT place_name, lat::float AS lat, lon::float AS lon FROM garden_settings WHERE id = 1").fetchone()
    return s if s and s["lat"] is not None else None


@router.get("/calendar/weather")
def weather():
    """The forecast for each event day in the next 16 days: at the event's place, else where you live. One forecast
    per place an hour at most (openmeteo.long_forecast); none if Open-Meteo can't be reached."""
    with db() as conn:
        now = today(conn)
        events = occurrences(conn, now, now + timedelta(days=15))
        where = home(conn)
    out, problems = [], set()
    for e in events:
        lat, lon = (e["lat"], e["lon"]) if e["lat"] is not None else ((where["lat"], where["lon"]) if where else (None, None))
        if lat is None:
            continue
        try:
            days = {d["day"]: d for d in openmeteo.long_forecast(lat, lon)}
        except openmeteo.WeatherError as err:
            problems.add(str(err))
            continue
        d = days.get(e["day"].isoformat())
        if d:
            out.append({"event_id": e["event_id"], "day": e["day"], **{k: d[k] for k in ("sky", "icon", "max", "min", "rain_chance")}})
    return {"weather": out, "error": next(iter(problems), None), "home": where["place_name"] if where else None}


# ---------------------------------------------------------------- balance, the year
DONE_MINUTES = {   # hobby -> minutes done per day, from that hobby's own log (others keep no time: sessions only)
    "models": "SELECT ended_at::date AS day, sum(extract(epoch FROM ended_at - started_at) / 60)::int AS minutes "
              "FROM model_sessions WHERE ended_at IS NOT NULL GROUP BY 1",
    "boardgames": "SELECT played_on AS day, sum(minutes) AS minutes FROM board_game_plays WHERE minutes IS NOT NULL GROUP BY 1",
    "hiking": "SELECT hiked_on AS day, sum(COALESCE(moving_s, elapsed_s) / 60) AS minutes FROM hikes "
              "WHERE COALESCE(moving_s, elapsed_s) IS NOT NULL GROUP BY 1",
    "reading": "SELECT logged_on AS day, sum(minutes) AS minutes FROM reading_log WHERE minutes IS NOT NULL GROUP BY 1",
    # (vg_playtime holds each game's running TOTAL: a day's playing is the change - vgplaytime.PLAYED)
    "videogames": f"SELECT day, sum(played) AS minutes FROM ({vgplaytime.PLAYED}) p GROUP BY 1",
}


def _minutes(e: dict) -> int:
    if not (e["start_time"] and e["end_time"]):
        return 0
    return max(0, (datetime.combine(e["day"], e["end_time"]) - datetime.combine(e["day"], e["start_time"])).seconds // 60)


@router.get("/calendar/balance")
def balance(start: date, end: date):
    """Per hobby between two days: events planned (and their minutes, where they have times) against sessions done
    (days its log has something) and minutes done (where the hobby keeps time)."""
    if end < start or (end - start).days > MAX_DAYS:
        raise HTTPException(422, f"The end must be after the start, and at most {MAX_DAYS} days later.")
    rows = defaultdict(lambda: {"planned_events": 0, "planned_minutes": 0, "done_days": 0, "done_minutes": None})
    with db() as conn:
        for e in occurrences(conn, start, end):
            if e["hobby"]:
                r = rows[e["hobby"]]
                r["planned_events"] += 1
                r["planned_minutes"] += _minutes(e)
        days = defaultdict(set)
        for a in activity.rows(conn, 5000, start, end):
            if a["kind"] in KIND_HOBBY:
                days[KIND_HOBBY[a["kind"]]].add(a["day"])
        for hobby, on in days.items():
            rows[hobby]["done_days"] = len(on)
        for hobby, sql in DONE_MINUTES.items():
            got = conn.execute(f"SELECT COALESCE(sum(minutes), 0)::int AS m FROM ({sql}) x WHERE day BETWEEN %s AND %s",
                               (start, end)).fetchone()["m"]
            if got or hobby in rows:
                rows[hobby]["done_minutes"] = got
    order = {h: i for i, h in enumerate(MODULE_IDS)}
    return [{"hobby": h, **r} for h, r in sorted(rows.items(), key=lambda kv: order.get(kv[0], 99))
            if r["planned_events"] or r["done_days"] or r["done_minutes"]]


@router.get("/calendar/year")
def year(year: int = Query(..., ge=2000, le=2100)):
    """A year day by day: how many things you did (and in which hobbies), the day's mood, and the holidays."""
    start, end = date(year, 1, 1), date(year, 12, 31)
    with db() as conn:
        did = activity.rows(conn, 20000, start, end)
        moods = {m["day"]: m["mood"] for m in conn.execute(
            "SELECT DISTINCT ON (entry_date) entry_date AS day, mood FROM journal_pages WHERE mood IS NOT NULL "
            "AND entry_date BETWEEN %s AND %s ORDER BY entry_date, updated_at DESC", (start, end)).fetchall()}
    days = defaultdict(lambda: {"count": 0, "hobbies": set()})
    for a in did:
        if a["kind"] in ("supply", "page"):
            continue
        d = days[a["day"]]
        d["count"] += 1
        if a["kind"] in KIND_HOBBY:
            d["hobbies"].add(KIND_HOBBY[a["kind"]])
    every = sorted(set(days) | set(moods))
    return {"year": year, "holidays": holidays_between(start, end),
            "days": [{"day": d, "count": days[d]["count"] if d in days else 0,
                      "hobbies": sorted(days[d]["hobbies"]) if d in days else [], "mood": moods.get(d)} for d in every]}


# ---------------------------------------------------------------- what to bring
@router.get("/calendar/bring")
def bring(hobby: str | None = None):
    """What an event's checklist can be filled from: that hobby's gear (rifles and ammo for shooting) and every
    packing list (Travel's)."""
    with db() as conn:
        gear = []
        if hobby == "shooting":
            gear = [r["name"] for r in conn.execute("SELECT name FROM rifles ORDER BY name").fetchall()] + \
                   [r["name"] for r in conn.execute("SELECT name FROM ammo ORDER BY name").fetchall()]
        elif hobby:
            gear = [r["name"] for r in conn.execute("SELECT name FROM gear WHERE hobby = %s AND condition <> 'Retired' "
                                                    "ORDER BY kind NULLS LAST, name", (hobby,)).fetchall()]
        lists = [{"name": r["name"], "items": [i["name"] for i in r["items"] if i.get("name")]}
                 for r in conn.execute("SELECT name, items FROM packing_lists ORDER BY name").fetchall()]
    return {"gear": gear, "packing_lists": lists}


# ---------------------------------------------------------------- move (drag)
class MoveIn(BaseModel):
    from_day: date
    to_day: date
    start_time: time | None = None
    end_time: time | None = None
    keep_time: bool = True           # false: start_time / end_time as given (a drop on the week's hours)


@router.post("/calendar/events/{event_id}/move")
def move(event_id: int, body: MoveIn):
    """Move an event's day (and time, from the week view). One day of a repeating event moves on its own: that day is
    skipped and a one-off copy is made on the new day."""
    with db() as conn:
        e = fetch_event(conn, event_id)
        if body.from_day not in days_of(e, body.from_day, body.from_day):
            raise HTTPException(409, "The event isn't on that day.")
        times = {} if body.keep_time else {"start_time": body.start_time, "end_time": body.end_time}
        if times.get("end_time") and times.get("start_time") and times["end_time"] <= times["start_time"]:
            times["end_time"] = None
        if e["repeats"] == "never":
            update_row(conn, "calendar_events", "event_id", event_id, {"starts_on": body.to_day, **times})
            return fetch_event(conn, event_id)
        conn.execute("UPDATE calendar_events SET skipped = array_append(skipped, %s) WHERE event_id = %s",
                     (body.from_day, event_id))
        copy = {k: e[k] for k in ("title", "hobby", "start_time", "end_time", "location", "notes", "lat", "lon", "countdown")}
        copy.update(starts_on=body.to_day, repeats="never", checklist=Jsonb(e["checklist"]), **times)
        return fetch_event(conn, insert_row(conn, "calendar_events", copy, "event_id"))
