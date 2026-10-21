"""More for the journal (2026-10-21, from a look at Day One, Apple Journal, Notion and reMarkable):

    on this day   pages from this day in earlier years, and what you did then           GET /journal/on-this-day
    today         what the app saw you do today - things to write about                 GET /journal/today
    calendar      a month: each day's pages and mood, and your writing streak            GET /journal/calendar
    insights      mood over time, and mood on the days you did each hobby                GET /journal/insights
    review        a week (or month): moods, what you did, goals - for a review page      GET /journal/review
    notebooks     separate journals with a colour                                        /journal/notebooks
    templates     pages saved to start new ones from (built-in ones are in the web app)  /journal/templates
    weather       that day's weather where the page was written (Open-Meteo)             POST /journal/{id}/weather
    map           pages with a place                                                     GET /journal/places
    export        whole pages between two days, to print or save as a PDF               GET /journal/export

Private pages stay out of all of these except the calendar's counts (and their own notebook's export). Included
before journal.py's router: these fixed paths would otherwise be read as /journal/{page_id}.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import activity, openmeteo
from .db import db, found, insert_row, update_row
from .journal import PAGE_LIST, fetch_page

router = APIRouter(prefix="/api", tags=["journal"])

SCORE = {"great": 5, "good": 4, "okay": 3, "meh": 2, "rough": 1}
# The activity feed's kinds, by hobby (insights and reviews group by these; a page written isn't an activity here).
HOBBY = {"model": "Models", "game": "Board games", "volleyball": "Volleyball", "videogame": "Video games", "chess": "Chess",
         "book": "Reading", "hike": "Hiking", "shoot": "Precision shooting", "trip": "Travel", "planting": "Gardening",
         "gcontainer": "Gardening", "gspace": "Gardening", "goal": "Goals", "supply": "Supplies", "gear": "Gear"}
NOT_A_HOBBY = {"Goals", "Supplies", "Gear"}         # (insights: mood on hobby days only)
COLOURS = ("teal", "purple", "ok", "low", "tint", "out")


def today(conn) -> date:
    return conn.execute("SELECT current_date AS d").fetchone()["d"]     # Brisbane, not the container's UTC


def did_on(conn, start: date, end: date, limit: int = 2000, skip=("page",)) -> list[dict]:
    """What the activity feed has between two days (whole days), without journal pages (and whatever else `skip` says)."""
    return [r for r in activity.rows(conn, limit, start, end) if r["kind"] not in skip]


NOT_TO_WRITE_ABOUT = ("page", "supply")      # to write about: not the stock you added or used (Write about today, On this day)


# ---------------------------------------------------------------- on this day, today
@router.get("/journal/on-this-day")
def on_this_day(day: date | None = None, years: int = Query(5, ge=1, le=20)):
    """For each earlier year (up to `years` back) with something on this day: its pages and what you did."""
    with db() as conn:
        day = day or today(conn)
        out = []
        for back in range(1, years + 1):
            try:
                then = day.replace(year=day.year - back)
            except ValueError:                          # 29 February in a year without one
                continue
            pages = conn.execute(PAGE_LIST + " WHERE p.entry_date = %s AND NOT p.private ORDER BY p.page_id",
                                 (then,)).fetchall()
            did = did_on(conn, then, then, 30, NOT_TO_WRITE_ABOUT)
            if pages or did:
                out.append({"day": then, "years_ago": back, "pages": pages, "did": did[:6]})
        return out


@router.get("/journal/today")
def today_to_write(day: date | None = None):
    """What you did on a day (default today), to write about, and the pages already about it."""
    with db() as conn:
        day = day or today(conn)
        pages = conn.execute("SELECT page_id, title, kind FROM journal_pages WHERE entry_date = %s AND NOT private "
                             "ORDER BY page_id", (day,)).fetchall()
        return {"day": day, "did": did_on(conn, day, day, 60, NOT_TO_WRITE_ABOUT), "pages": pages}


# ---------------------------------------------------------------- calendar and streaks
def streaks(days: set[date], now: date) -> dict:
    """The run of days with a page up to today (or yesterday: today isn't over), and the longest run ever."""
    current, d = 0, now if now in days else now - timedelta(days=1)
    while d in days:
        current += 1
        d -= timedelta(days=1)
    longest = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        longest = max(longest, run)
        prev = d
    return {"current": current, "longest": longest, "today": now in days}


@router.get("/journal/calendar")
def calendar(month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    """A month of the journal: each day's pages (count, the first one), its mood, and your writing streak."""
    start = date.fromisoformat(f"{month}-01")
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    with db() as conn:
        rows = conn.execute("""
            SELECT entry_date AS day, count(*) AS pages, (array_agg(page_id ORDER BY page_id))[1] AS page_id,
                   (array_agg(mood ORDER BY updated_at DESC) FILTER (WHERE mood IS NOT NULL))[1] AS mood
            FROM journal_pages WHERE entry_date BETWEEN %s AND %s GROUP BY entry_date ORDER BY entry_date""",
                            (start, end)).fetchall()
        written = {r["day"] for r in conn.execute("SELECT DISTINCT entry_date AS day FROM journal_pages").fetchall()}
        return {"month": month, "days": rows, "streak": streaks(written, today(conn))}


# ---------------------------------------------------------------- insights
@router.get("/journal/insights")
def insights(days: int = Query(90, ge=7, le=730)):
    """How you've felt: each week's average mood (1 rough - 5 great), the mood on days you did each hobby compared
    with your usual, the words you use most, and how much you wrote. A hobby needs 3 days with a mood to count."""
    with db() as conn:
        end = today(conn)
        start = end - timedelta(days=days - 1)
        moods = conn.execute(
            "SELECT DISTINCT ON (entry_date) entry_date AS day, mood FROM journal_pages "
            "WHERE mood IS NOT NULL AND entry_date BETWEEN %s AND %s ORDER BY entry_date, updated_at DESC",
            (start, end)).fetchall()
        words = conn.execute(
            "SELECT w AS word, count(*) AS n FROM journal_pages, unnest(mood_words) w "
            "WHERE entry_date BETWEEN %s AND %s GROUP BY w ORDER BY n DESC, w LIMIT 12", (start, end)).fetchall()
        counts = conn.execute(
            "SELECT count(*) AS pages, count(DISTINCT entry_date) AS writing_days FROM journal_pages "
            "WHERE entry_date BETWEEN %s AND %s", (start, end)).fetchone()
        did = did_on(conn, start, end, 5000)
    score = {m["day"]: SCORE[m["mood"]] for m in moods}
    usual = round(sum(score.values()) / len(score), 2) if score else None

    weeks = defaultdict(list)
    for d, s in score.items():
        weeks[d - timedelta(days=d.weekday())].append(s)
    weekly = [{"week": w, "average": round(sum(v) / len(v), 2), "days": len(v)} for w, v in sorted(weeks.items())]

    hobby_days = defaultdict(set)
    for r in did:
        label = HOBBY.get(r["kind"])
        if label and label not in NOT_A_HOBBY:
            hobby_days[label].add(r["day"])
    by_hobby = []
    for label, on in hobby_days.items():
        felt = [score[d] for d in on if d in score]
        if len(felt) >= 3 and usual is not None:
            average = round(sum(felt) / len(felt), 2)
            by_hobby.append({"hobby": label, "days": len(felt), "average": average, "vs_usual": round(average - usual, 2)})
    by_hobby.sort(key=lambda h: -h["vs_usual"])
    return {"start": start, "end": end, "usual": usual, "mood_days": len(score), "weekly": weekly,
            "spread": Counter(m["mood"] for m in moods), "by_hobby": by_hobby, "words": words, **counts}


# ---------------------------------------------------------------- review
@router.get("/journal/review")
def review(start: date, end: date):
    """A week (or a month) at a glance, for a review page: each day's mood, what you did by hobby, goals reached and
    moved, and the pages you wrote."""
    if end < start or (end - start).days > 62:
        raise HTTPException(422, "The end must be after the start, and at most two months later.")
    with db() as conn:
        moods = conn.execute(
            "SELECT DISTINCT ON (entry_date) entry_date AS day, mood, mood_words FROM journal_pages "
            "WHERE mood IS NOT NULL AND entry_date BETWEEN %s AND %s ORDER BY entry_date, updated_at DESC",
            (start, end)).fetchall()
        pages = conn.execute(PAGE_LIST + " WHERE p.entry_date BETWEEN %s AND %s AND NOT p.private "
                             "ORDER BY p.entry_date, p.page_id", (start, end)).fetchall()
        did = did_on(conn, start, end, 2000, NOT_TO_WRITE_ABOUT)
    by_hobby = defaultdict(list)
    for r in sorted(did, key=lambda r: r["at"]):
        if r["kind"] != "goal":
            by_hobby[HOBBY.get(r["kind"], "Other")].append(r)
    goals = [r for r in did if r["kind"] == "goal"]
    return {"start": start, "end": end, "moods": moods, "pages": pages, "goals": goals,
            "hobbies": [{"hobby": h, "count": len(items), "items": items[:12]}
                        for h, items in sorted(by_hobby.items(), key=lambda kv: -len(kv[1]))]}


# ---------------------------------------------------------------- notebooks
class NotebookIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    colour: Literal[COLOURS] = "teal"


class NotebookPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=40)
    colour: Literal[COLOURS] | None = None


@router.get("/journal/notebooks")
def notebooks():
    """Your notebooks, with how many pages each has (private ones included in the count)."""
    with db() as conn:
        return conn.execute("SELECT n.notebook_id, n.name, n.colour, count(p.page_id) AS pages FROM journal_notebooks n "
                            "LEFT JOIN journal_pages p USING (notebook_id) GROUP BY n.notebook_id ORDER BY lower(n.name)").fetchall()


@router.post("/journal/notebooks", status_code=201)
def add_notebook(body: NotebookIn):
    with db() as conn:
        notebook_id = insert_row(conn, "journal_notebooks", {"name": body.name.strip(), "colour": body.colour}, "notebook_id")
        return conn.execute("SELECT notebook_id, name, colour, 0 AS pages FROM journal_notebooks WHERE notebook_id = %s",
                            (notebook_id,)).fetchone()


@router.patch("/journal/notebooks/{notebook_id}")
def change_notebook(notebook_id: int, body: NotebookPatch):
    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    with db() as conn:
        found(conn.execute("SELECT 1 FROM journal_notebooks WHERE notebook_id = %s", (notebook_id,)).fetchone(), "Notebook")
        update_row(conn, "journal_notebooks", "notebook_id", notebook_id, data)
    return next(n for n in notebooks() if n["notebook_id"] == notebook_id)


@router.delete("/journal/notebooks/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: int):
    """The notebook goes; its pages stay, in no notebook."""
    with db() as conn:
        found(conn.execute("DELETE FROM journal_notebooks WHERE notebook_id = %s RETURNING 1", (notebook_id,)).fetchone(),
              "Notebook")
    return Response(status_code=204)


# ---------------------------------------------------------------- templates
class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    title: str = Field("", max_length=200)
    content: list = []
    tags: list[str] = Field([], max_length=20)


@router.get("/journal/templates")
def templates():
    with db() as conn:
        return conn.execute("SELECT * FROM journal_templates ORDER BY lower(name)").fetchall()


@router.post("/journal/templates", status_code=201)
def add_template(body: TemplateIn):
    """Save a page's blocks (its title and tags too) as a template for new pages."""
    with db() as conn:
        template_id = insert_row(conn, "journal_templates", {"name": body.name.strip(), "title": body.title,
                                 "content": Jsonb(body.content), "tags": [t.strip() for t in body.tags if t.strip()]},
                                 "template_id")
        return conn.execute("SELECT * FROM journal_templates WHERE template_id = %s", (template_id,)).fetchone()


@router.delete("/journal/templates/{template_id}", status_code=204)
def delete_template(template_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM journal_templates WHERE template_id = %s RETURNING 1", (template_id,)).fetchone(),
              "Template")
    return Response(status_code=204)


# ---------------------------------------------------------------- weather, map, export
def home_place(conn) -> dict | None:
    """Where you are when a page has no place of its own: Gardening's setting (Settings there: "Where you are")."""
    s = conn.execute("SELECT place_name, lat::float AS lat, lon::float AS lon FROM garden_settings WHERE id = 1").fetchone()
    return s if s and s["lat"] is not None else None


@router.post("/journal/{page_id}/weather")
def stamp_weather(page_id: int):
    """Put that day's weather on the page: where the page was written, else where you live. Open-Meteo keeps the
    last three months, so an older page can't have it."""
    with db() as conn:
        page = fetch_page(conn, page_id)
        place = {"place_name": page["place_name"], "lat": page["lat"], "lon": page["lon"]} if page["lat"] is not None \
            else home_place(conn)
        if not place:
            raise HTTPException(409, "Give the page a place first (or set where you are in Gardening's settings).")
        age = (today(conn) - page["entry_date"]).days
    if age > 92 or age < -14:
        raise HTTPException(422, "Weather is only kept for the last three months (and the next two weeks).")
    try:
        weather = openmeteo.day_weather(place["lat"], place["lon"], page["entry_date"].isoformat())
    except openmeteo.WeatherError as e:
        raise HTTPException(502, str(e)) from None
    if not weather:
        raise HTTPException(404, "Open-Meteo has no weather for that day.")
    with db() as conn:
        changes = {"weather": Jsonb(weather)}
        if page["lat"] is None:                         # it was written at home
            changes.update(place_name=place["place_name"], lat=place["lat"], lon=place["lon"])
        update_row(conn, "journal_pages", "page_id", page_id, changes)
        return fetch_page(conn, page_id)


@router.get("/journal/home-place")
def where_you_are():
    """Where you live (from Gardening's settings), or null: new pages can be placed there."""
    with db() as conn:
        return home_place(conn)


@router.get("/journal/places")
def places():
    """Pages with a place, for the journal's map (not private ones)."""
    with db() as conn:
        return conn.execute(PAGE_LIST + " WHERE p.lat IS NOT NULL AND NOT p.private ORDER BY p.entry_date DESC").fetchall()


@router.get("/journal/export")
def export(start: date, end: date, notebook: int | None = None, private: bool = False):
    """Whole pages between two days, oldest first, to print (or save as a PDF from the print window). Private pages
    only with private=true."""
    if end < start or (end - start).days > 400:
        raise HTTPException(422, "The end must be after the start, and at most 400 days later.")
    where, params = ["p.entry_date BETWEEN %s AND %s"], [start, end]
    if not private:
        where.append("NOT p.private")
    if notebook is not None:
        where.append("p.notebook_id = %s")
        params.append(notebook)
    with db() as conn:
        ids = [r["page_id"] for r in conn.execute(
            "SELECT page_id FROM journal_pages p WHERE " + " AND ".join(where) + " ORDER BY entry_date, page_id LIMIT 500",
            params).fetchall()]
        return [fetch_page(conn, i) for i in ids]
