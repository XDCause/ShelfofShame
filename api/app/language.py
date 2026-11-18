"""Language learning (a hobby module, 2026-11-17): the languages you're learning, your study log, input hours, resources,
the CEFR can-do checklist and the dashboard (A09_language.sql). The flashcards and reviews are in language_cards.py,
the scheduler in srs.py. No outside site is asked: pronunciation is the browser's own speech (speechSynthesis).

    GET  /language/lists                          the choices: levels, activities, resource kinds, milestones, can-dos
    GET / POST /language/languages, PATCH / DELETE /language/languages/{id}
    GET  /language/summary?language_id=           the dashboard and Home: streak, due cards, minutes today / this week
                                                  against the goal, input hours and the next milestone, retention,
                                                  words known, the last 7 days and 12 weeks of minutes
    GET  /language/stats?language_id=             minutes a week, by activity, reviews a day, cards by state, what's due
    GET / POST /language/study, PATCH / DELETE /language/study/{id}           the study log
    GET / POST /language/resources, PATCH / DELETE /language/resources/{id}   books, shows, podcasts...
    GET  /language/languages/{id}/cando, PUT /language/languages/{id}/cando/{item}   the can-do checklist

Minutes studied = the study log + time spent reviewing cards (each answer up to a minute) + the course's lessons
(language_course.py), so the daily goal moves with reviews and lessons too. Input hours (Refold / Dreaming Spanish style: hours of understandable listening, watching and
reading, plus tutor and class time - conversation counts, as their "crosstalk" does) add up toward MILESTONES; hours
from before the app go on the language (prior_input_hours).
"""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row
from .videogames import streaks

router = APIRouter(prefix="/api", tags=["language"])

LEVELS = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
GOAL_LEVELS = LEVELS[1:]
ACTIVITIES = ["App", "Class", "Tutor", "Reading", "Listening", "Watching", "Speaking", "Writing", "Grammar", "Other"]
INPUT_ACTIVITIES = ("Listening", "Watching", "Reading", "Tutor", "Class")
RESOURCE_KINDS = ["Book", "Textbook", "Show", "Film", "Podcast", "YouTube", "App", "Course", "Website", "Music", "Other"]
RESOURCE_STATUSES = ["Want", "Using", "Done", "Dropped"]
# Dreaming Spanish's levels for an English speaker learning Spanish (a closely related language takes about half).
MILESTONES = [(50, "Level 2: you start to follow very easy, slow input"), (150, "Level 3: you follow easy topics"),
              (300, "Level 4: you understand patient speakers - a good time to start reading"),
              (600, "Level 5: everyday topics at a normal pace - a good time to start speaking"),
              (1000, "Level 6: comfortable with daily conversation"), (1500, "Level 7: native content, most of it")]
MATURE_DAYS = 21          # a card you'd remember three weeks on is a word you know (Anki's "mature")

# The CEFR can-do checklist: what each level means in practice, in our own words (after the Council of Europe's
# global scale - its wording isn't copied). Keys: level-topic.
CANDO = [
    ("a1-introduce", "A1", "Introduce yourself and say where you're from and what you do"),
    ("a1-questions", "A1", "Ask and answer simple questions about people, places and things you have"),
    ("a1-numbers", "A1", "Understand prices, times and numbers when they're said slowly"),
    ("a1-forms", "A1", "Fill in a form with your name, address and nationality"),
    ("a2-routine", "A2", "Describe your day, your family and your work in simple sentences"),
    ("a2-shopping", "A2", "Order food, buy things and ask for directions"),
    ("a2-gist", "A2", "Catch the point of short, clear announcements and messages"),
    ("a2-past", "A2", "Say what you did last weekend"),
    ("b1-travel", "B1", "Handle most situations when travelling where it's spoken"),
    ("b1-opinions", "B1", "Give your opinion and the reasons for it, and talk about plans and hopes"),
    ("b1-stories", "B1", "Tell a story or the plot of a film or book"),
    ("b1-familiar", "B1", "Follow the main points of clear talk about familiar things (work, school, free time)"),
    ("b2-natives", "B2", "Talk with native speakers at a normal pace without strain on either side"),
    ("b2-news", "B2", "Follow most TV news, films in standard speech and articles on current affairs"),
    ("b2-argue", "B2", "Argue a point of view, weighing the pros and cons"),
    ("b2-detail", "B2", "Write clear, detailed text on a wide range of subjects"),
    ("c1-implicit", "C1", "Understand long, demanding texts and pick up implicit meaning"),
    ("c1-fluent", "C1", "Express yourself fluently without obviously searching for words"),
    ("c1-work", "C1", "Use the language flexibly at work or in study"),
    ("c2-everything", "C2", "Understand virtually everything you hear or read"),
    ("c2-nuance", "C2", "Express fine shades of meaning precisely, even in complex situations"),
    ("c2-summarise", "C2", "Summarise from different spoken and written sources, coherently"),
]
CANDO_KEYS = {k for k, _, _ in CANDO}

Level = Literal[tuple(LEVELS)]
GoalLevel = Literal[tuple(GOAL_LEVELS)]
Activity = Literal[tuple(ACTIVITIES)]
ResourceKind = Literal[tuple(RESOURCE_KINDS)]
ResourceStatus = Literal[tuple(RESOURCE_STATUSES)]
VOICE = r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$"


@router.get("/language/lists")
def lists():
    return {"levels": LEVELS, "goal_levels": GOAL_LEVELS, "activities": ACTIVITIES, "input_activities": list(INPUT_ACTIVITIES),
            "resource_kinds": RESOURCE_KINDS, "resource_statuses": RESOURCE_STATUSES,
            "milestones": [{"hours": h, "what": w} for h, w in MILESTONES],
            "cando": [{"item": k, "level": lv, "text": t} for k, lv, t in CANDO]}


def language_exists(conn, language_id: int):
    if not conn.execute("SELECT 1 FROM lang_languages WHERE language_id = %s", (language_id,)).fetchone():
        raise HTTPException(422, "There's no such language.")


# ---------------------------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------------------------
class LanguageFields(BaseModel):
    voice: str | None = Field(None, max_length=35, pattern=VOICE)
    level: Level | None = None
    goal_level: GoalLevel | None = None
    goal_date: date | None = None
    why: str | None = Field(None, max_length=2000)
    daily_minutes: int | None = Field(None, ge=1, le=600)
    new_per_day: int | None = Field(None, ge=0, le=200)
    prior_input_hours: float | None = Field(None, ge=0, le=20000)
    active: bool | None = None
    started_on: date | None = None
    course: str | None = Field(None, pattern=r"^[a-z]{2,3}$")     # a built-in course (language_course.py), None = none


class LanguageIn(LanguageFields):
    name: str = Field(min_length=1, max_length=60)


class LanguagePatch(LanguageFields):
    name: str | None = Field(None, min_length=1, max_length=60)


INPUT_SQL = "'" + "', '".join(INPUT_ACTIVITIES) + "'"
LANGUAGE_SELECT = f"""SELECT l.language_id, l.name, l.voice, l.level, l.goal_level, l.goal_date, l.why, l.daily_minutes,
       l.new_per_day, l.prior_input_hours::float AS prior_input_hours, l.active, l.started_on, l.course,
       (SELECT count(*) FROM lang_cards c WHERE c.language_id = l.language_id)::int AS cards,
       (SELECT count(*) FROM lang_cards c WHERE c.language_id = l.language_id AND c.state = 'review'
            AND c.stability >= {MATURE_DAYS})::int AS words_known,
       round((l.prior_input_hours + COALESCE((SELECT sum(s.minutes) FROM lang_study s WHERE s.language_id = l.language_id
            AND s.activity IN ({INPUT_SQL})), 0) / 60.0)::numeric, 1)::float AS input_hours
FROM lang_languages l"""


@router.get("/language/languages")
def list_languages():
    with db() as conn:
        return conn.execute(LANGUAGE_SELECT + " ORDER BY l.active DESC, l.created_at").fetchall()


@router.post("/language/languages", status_code=201)
def add_language(body: LanguageIn):
    from .language_course import course_exists, course_for_name
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("name",))
    if "course" not in body.model_fields_set:
        data["course"] = course_for_name(data["name"])      # Spanish / Español: the Spanish course by itself
    course_exists(data.get("course"))
    with db() as conn:
        if conn.execute("SELECT 1 FROM lang_languages WHERE lower(name) = lower(%s)", (data["name"],)).fetchone():
            raise HTTPException(409, "You're already learning that language.")
        language_id = insert_row(conn, "lang_languages", data, "language_id")
        return conn.execute(LANGUAGE_SELECT + " WHERE l.language_id = %s", (language_id,)).fetchone()


@router.patch("/language/languages/{language_id}")
def update_language(language_id: int, body: LanguagePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("name",))
    for required in ("name", "daily_minutes", "new_per_day", "prior_input_hours", "active", "started_on"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    if data.get("course") is not None:
        from .language_course import course_exists
        course_exists(data["course"])
    with db() as conn:
        found(conn.execute("SELECT 1 FROM lang_languages WHERE language_id = %s", (language_id,)).fetchone(), "Language")
        if "name" in data and conn.execute("SELECT 1 FROM lang_languages WHERE lower(name) = lower(%s) AND language_id <> %s",
                                           (data["name"], language_id)).fetchone():
            raise HTTPException(409, "You're already learning that language.")
        update_row(conn, "lang_languages", "language_id", language_id, data)
        return conn.execute(LANGUAGE_SELECT + " WHERE l.language_id = %s", (language_id,)).fetchone()


@router.delete("/language/languages/{language_id}", status_code=204)
def delete_language(language_id: int):
    """Remove a language with its cards, reviews, study log, resources and checklist."""
    with db() as conn:
        found(conn.execute("DELETE FROM lang_languages WHERE language_id = %s RETURNING language_id",
                           (language_id,)).fetchone(), "Language")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Minutes per day (the log + reviewing), the dashboard
# ---------------------------------------------------------------------------------------------
# One row per (day, language): minutes from the log, from reviews (each answer counts up to 60 s; none timed = 10 s) and
# from the course's lessons (each up to an hour: language_course.py).
MINUTES = """
SELECT day, language_id, sum(m)::float AS minutes, sum(input)::float AS input FROM (
    SELECT studied_on AS day, language_id, minutes::numeric AS m,
           CASE WHEN activity IN ({input}) THEN minutes ELSE 0 END AS input
    FROM lang_study
  UNION ALL
    SELECT r.reviewed_at::date, c.language_id, least(COALESCE(r.seconds, 10), 60) / 60.0, 0
    FROM lang_reviews r JOIN lang_cards c USING (card_id)
  UNION ALL
    SELECT done_at::date, language_id, least(seconds, 3600) / 60.0, 0 FROM lang_lesson_runs
) x GROUP BY day, language_id""".format(input=INPUT_SQL)


def _which(language_id: int | None, alias: str = "language_id") -> tuple[str, tuple]:
    return (f" AND {alias} = %s", (language_id,)) if language_id is not None else ("", ())


def due_counts(conn, language_id: int | None = None) -> dict:
    """Cards to review today (due before midnight) and new cards still allowed today, per language."""
    where, args = _which(language_id, "l.language_id")
    rows = conn.execute(f"""
        SELECT l.language_id,
               (SELECT count(*) FROM lang_cards c WHERE c.language_id = l.language_id AND NOT c.suspended
                    AND c.state <> 'new' AND c.due < (current_date + 1)::timestamptz)::int AS due,
               least((SELECT count(*) FROM lang_cards c WHERE c.language_id = l.language_id AND NOT c.suspended
                          AND c.state = 'new'),
                     greatest(0, l.new_per_day - (SELECT count(DISTINCT r.card_id) FROM lang_reviews r JOIN lang_cards c USING (card_id)
                          WHERE c.language_id = l.language_id AND r.state_before = 'new'
                            AND r.reviewed_at >= current_date::timestamptz)))::int AS new
        FROM lang_languages l WHERE l.active{where}""", args).fetchall()
    return {r["language_id"]: {"due": r["due"], "new": r["new"]} for r in rows}


def _milestones(hours: float) -> dict:
    reached = [{"hours": h, "what": w} for h, w in MILESTONES if hours >= h]
    nxt = next(({"hours": h, "what": w, "to_go": round(h - hours, 1)} for h, w in MILESTONES if hours < h), None)
    return {"reached": reached, "next": nxt}


@router.get("/language/summary")
def summary(language_id: int | None = Query(None, ge=1, le=2147483647)):
    """The dashboard (one language, or all of them for Home)."""
    with db() as conn:
        today = conn.execute("SELECT current_date AS d").fetchone()["d"]
        where, args = _which(language_id, "l.language_id")
        languages = conn.execute(LANGUAGE_SELECT + f" WHERE true{where} ORDER BY l.active DESC, l.created_at", args).fetchall()
        if language_id is not None and not languages:
            found(None, "Language")
        due = due_counts(conn, language_id)
        mwhere, margs = _which(language_id)
        days = conn.execute(f"SELECT * FROM ({MINUTES}) m WHERE day > current_date - 84{mwhere}", margs).fetchall()
        all_days = conn.execute(f"SELECT DISTINCT day FROM ({MINUTES}) m WHERE minutes > 0{mwhere}", margs).fetchall()
        rwhere, rargs = _which(language_id, "c.language_id")
        # retention: of the answers to cards already in review (not still being learned), the last 30 days
        mature = conn.execute(f"""
            SELECT count(*) FILTER (WHERE r.state_before = 'review')::int AS n,
                   count(*) FILTER (WHERE r.state_before = 'review' AND r.grade > 1)::int AS ok,
                   count(*) FILTER (WHERE r.reviewed_at >= current_date::timestamptz)::int AS today
            FROM lang_reviews r JOIN lang_cards c USING (card_id) WHERE r.reviewed_at > now() - interval '30 days'{rwhere}""",
            rargs).fetchone()
        recent = conn.execute(STUDY_SELECT + f" WHERE true{_which(language_id, 's.language_id')[0]} "
                              "ORDER BY s.studied_on DESC, s.study_id DESC LIMIT 6", args).fetchall()

    per_day: dict[date, float] = {}
    for d in days:
        per_day[d["day"]] = per_day.get(d["day"], 0) + d["minutes"]
    week_start = today - timedelta(days=today.weekday())
    for lang in languages:
        lang.update(due.get(lang["language_id"], {"due": 0, "new": 0}))
        lang["minutes_today"] = round(sum(d["minutes"] for d in days if d["day"] == today and d["language_id"] == lang["language_id"]))
        lang["minutes_week"] = round(sum(d["minutes"] for d in days if d["day"] >= week_start and d["language_id"] == lang["language_id"]))
        lang["milestones"] = _milestones(lang["input_hours"])
    active = [lang for lang in languages if lang["active"]]
    goal_day = sum(lang["daily_minutes"] for lang in active)
    input_hours = round(sum(lang["input_hours"] for lang in languages), 1)
    return {
        "today": today,
        "languages": languages,
        "due": sum(lang["due"] for lang in languages),
        "new": sum(lang["new"] for lang in languages),
        "reviews_today": mature["today"],
        "minutes_today": round(per_day.get(today, 0)),
        "minutes_week": round(sum(m for d, m in per_day.items() if d >= week_start)),
        "goal_day": goal_day,
        "goal_week": goal_day * 7,
        "streak": streaks([d["day"] for d in all_days], today),
        "input_hours": input_hours,
        "milestones": _milestones(input_hours) if language_id is not None else None,
        "words_known": sum(lang["words_known"] for lang in languages),
        "cards": sum(lang["cards"] for lang in languages),
        "retention": round(100 * mature["ok"] / mature["n"]) if mature["n"] else None,
        "retention_reviews": mature["n"],
        # the last 84 days (12 weeks, Monday first, ending this week), each with its minutes
        "days": [{"day": d, "minutes": round(per_day.get(d, 0))}
                 for d in (week_start - timedelta(weeks=11) + timedelta(days=i) for i in range(84))],
        "recent": recent,
    }


@router.get("/language/stats")
def stats(language_id: int | None = Query(None, ge=1, le=2147483647)):
    """Minutes a week (12 weeks), minutes by activity (all time and the last 30 days), reviews a day (30 days, with how
    many were remembered), cards by state, and how many come due each of the next 14 days."""
    mwhere, margs = _which(language_id)
    cwhere, cargs = _which(language_id, "c.language_id")
    swhere, sargs = _which(language_id, "s.language_id")
    with db() as conn:
        weeks = conn.execute(f"""
            SELECT date_trunc('week', day)::date AS week, round(sum(minutes))::int AS minutes, round(sum(input))::int AS input
            FROM ({MINUTES}) m WHERE day >= date_trunc('week', current_date)::date - 77{mwhere} GROUP BY 1 ORDER BY 1""",
            margs).fetchall()
        by_activity = conn.execute(f"""
            SELECT activity, sum(minutes)::int AS minutes,
                   COALESCE(sum(minutes) FILTER (WHERE studied_on > current_date - 30), 0)::int AS recent
            FROM lang_study s WHERE true{swhere} GROUP BY activity ORDER BY 2 DESC""", sargs).fetchall()
        reviews = conn.execute(f"""
            SELECT r.reviewed_at::date AS day, count(*)::int AS reviews, count(*) FILTER (WHERE r.grade > 1)::int AS remembered,
                   count(*) FILTER (WHERE r.state_before = 'new')::int AS new
            FROM lang_reviews r JOIN lang_cards c USING (card_id)
            WHERE r.reviewed_at >= (current_date - 29)::timestamptz{cwhere} GROUP BY 1 ORDER BY 1""", cargs).fetchall()
        states = conn.execute(f"""
            SELECT CASE WHEN c.suspended THEN 'suspended' WHEN c.state = 'review' AND c.stability >= {MATURE_DAYS} THEN 'known'
                        ELSE c.state END AS state, count(*)::int AS cards
            FROM lang_cards c WHERE true{cwhere} GROUP BY 1""", cargs).fetchall()
        forecast = conn.execute(f"""
            SELECT greatest(c.due::date, current_date) AS day, count(*)::int AS cards
            FROM lang_cards c WHERE c.state <> 'new' AND NOT c.suspended AND c.due < (current_date + 14)::timestamptz{cwhere}
            GROUP BY 1 ORDER BY 1""", cargs).fetchall()
        hardest = conn.execute(f"""
            SELECT c.card_id, c.front, c.back, c.kind, c.lapses FROM lang_cards c
            WHERE c.lapses > 0{cwhere} ORDER BY c.lapses DESC, c.difficulty DESC NULLS LAST LIMIT 8""", cargs).fetchall()
    return {"weeks": weeks, "by_activity": by_activity, "reviews": reviews,
            "states": {r["state"]: r["cards"] for r in states}, "forecast": forecast, "hardest": hardest}


# ---------------------------------------------------------------------------------------------
# The study log
# ---------------------------------------------------------------------------------------------
class StudyFields(BaseModel):
    studied_on: date | None = None
    activity: Activity | None = None
    minutes: int | None = Field(None, ge=1, le=1440)
    resource_id: int | None = Field(None, ge=1, le=2147483647)
    with_whom: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=5000)


class StudyIn(StudyFields):
    language_id: int = Field(ge=1, le=2147483647)
    activity: Activity
    minutes: int = Field(ge=1, le=1440)


class StudyPatch(StudyFields):
    language_id: int | None = Field(None, ge=1, le=2147483647)


STUDY_SELECT = """SELECT s.study_id, s.language_id, l.name AS language, s.studied_on, s.activity, s.minutes, s.resource_id,
       r.title AS resource, r.kind AS resource_kind, s.with_whom, s.notes
FROM lang_study s JOIN lang_languages l USING (language_id) LEFT JOIN lang_resources r USING (resource_id)"""


def _resource_fits(conn, resource_id, language_id):
    if resource_id is not None and not conn.execute("SELECT 1 FROM lang_resources WHERE resource_id = %s AND language_id = %s",
                                                    (resource_id, language_id)).fetchone():
        raise HTTPException(422, "That resource isn't one of this language's.")


@router.get("/language/study")
def list_study(language_id: int | None = Query(None, ge=1, le=2147483647), activity: Activity | None = None,
               limit: int = Query(200, ge=1, le=2000)):
    where, args = _which(language_id, "s.language_id")
    if activity:
        where, args = where + " AND s.activity = %s", (*args, activity)
    with db() as conn:
        return conn.execute(STUDY_SELECT + f" WHERE true{where} ORDER BY s.studied_on DESC, s.study_id DESC LIMIT %s",
                            (*args, limit)).fetchall()


@router.post("/language/study", status_code=201)
def add_study(body: StudyIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=())
    with db() as conn:
        language_exists(conn, body.language_id)
        _resource_fits(conn, body.resource_id, body.language_id)
        study_id = insert_row(conn, "lang_study", data, "study_id")
        return conn.execute(STUDY_SELECT + " WHERE s.study_id = %s", (study_id,)).fetchone()


@router.get("/language/study/{study_id}")
def get_study(study_id: int):
    with db() as conn:
        return found(conn.execute(STUDY_SELECT + " WHERE s.study_id = %s", (study_id,)).fetchone(), "Study entry")


@router.patch("/language/study/{study_id}")
def update_study(study_id: int, body: StudyPatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=())
    for required in ("language_id", "studied_on", "activity", "minutes"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.replace('_', ' ').capitalize()} can't be empty.")
    with db() as conn:
        row = found(conn.execute("SELECT language_id, resource_id FROM lang_study WHERE study_id = %s", (study_id,)).fetchone(),
                    "Study entry")
        lang = data.get("language_id", row["language_id"])
        if "language_id" in data:
            language_exists(conn, lang)
        _resource_fits(conn, data.get("resource_id", row["resource_id"]), lang)
        update_row(conn, "lang_study", "study_id", study_id, data)
        return conn.execute(STUDY_SELECT + " WHERE s.study_id = %s", (study_id,)).fetchone()


@router.delete("/language/study/{study_id}", status_code=204)
def delete_study(study_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM lang_study WHERE study_id = %s RETURNING study_id", (study_id,)).fetchone(), "Study entry")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------------------------
class ResourceFields(BaseModel):
    kind: ResourceKind | None = None
    status: ResourceStatus | None = None
    level: GoalLevel | None = None
    url: str | None = Field(None, max_length=2000, pattern=r"^\s*(https?://\S+)?\s*$")
    progress: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=5000)


class ResourceIn(ResourceFields):
    language_id: int = Field(ge=1, le=2147483647)
    title: str = Field(min_length=1, max_length=200)


class ResourcePatch(ResourceFields):
    title: str | None = Field(None, min_length=1, max_length=200)


RESOURCE_SELECT = """SELECT r.resource_id, r.language_id, l.name AS language, r.title, r.kind, r.status, r.level, r.url,
       r.progress, r.notes,
       COALESCE((SELECT sum(s.minutes) FROM lang_study s WHERE s.resource_id = r.resource_id), 0)::int AS minutes,
       (SELECT max(s.studied_on) FROM lang_study s WHERE s.resource_id = r.resource_id) AS last_used
FROM lang_resources r JOIN lang_languages l USING (language_id)"""
STATUS_ORDER = "array_position(ARRAY['Using', 'Want', 'Done', 'Dropped'], r.status)"


@router.get("/language/resources")
def list_resources(language_id: int | None = Query(None, ge=1, le=2147483647)):
    where, args = _which(language_id, "r.language_id")
    with db() as conn:
        return conn.execute(RESOURCE_SELECT + f" WHERE true{where} ORDER BY {STATUS_ORDER}, last_used DESC NULLS LAST, lower(r.title)",
                            args).fetchall()


@router.post("/language/resources", status_code=201)
def add_resource(body: ResourceIn):
    data = tidy_text({k: v for k, v in body.model_dump().items() if v is not None}, required=("title",))
    with db() as conn:
        language_exists(conn, body.language_id)
        resource_id = insert_row(conn, "lang_resources", data, "resource_id")
        return conn.execute(RESOURCE_SELECT + " WHERE r.resource_id = %s", (resource_id,)).fetchone()


@router.patch("/language/resources/{resource_id}")
def update_resource(resource_id: int, body: ResourcePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    for required in ("title", "kind", "status"):
        if required in data and data[required] is None:
            raise HTTPException(422, f"{required.capitalize()} can't be empty.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM lang_resources WHERE resource_id = %s", (resource_id,)).fetchone(), "Resource")
        update_row(conn, "lang_resources", "resource_id", resource_id, data)
        return conn.execute(RESOURCE_SELECT + " WHERE r.resource_id = %s", (resource_id,)).fetchone()


@router.delete("/language/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: int):
    """Remove a resource; study time logged with it stays (without it)."""
    with db() as conn:
        found(conn.execute("DELETE FROM lang_resources WHERE resource_id = %s RETURNING resource_id", (resource_id,)).fetchone(),
              "Resource")
    return Response(status_code=204)


# ---------------------------------------------------------------------------------------------
# The can-do checklist
# ---------------------------------------------------------------------------------------------
class CanDoIn(BaseModel):
    done: bool


def _cando(conn, language_id: int) -> list[dict]:
    ticked = {r["item"]: r["done_on"] for r in conn.execute("SELECT item, done_on FROM lang_cando WHERE language_id = %s",
                                                             (language_id,)).fetchall()}
    return [{"item": k, "level": lv, "text": t, "done_on": ticked.get(k)} for k, lv, t in CANDO]


@router.get("/language/languages/{language_id}/cando")
def get_cando(language_id: int):
    with db() as conn:
        found(conn.execute("SELECT 1 FROM lang_languages WHERE language_id = %s", (language_id,)).fetchone(), "Language")
        return _cando(conn, language_id)


@router.put("/language/languages/{language_id}/cando/{item}")
def put_cando(language_id: int, item: str, body: CanDoIn):
    if item not in CANDO_KEYS:
        raise HTTPException(404, "No such can-do statement.")
    with db() as conn:
        found(conn.execute("SELECT 1 FROM lang_languages WHERE language_id = %s", (language_id,)).fetchone(), "Language")
        if body.done:
            conn.execute("INSERT INTO lang_cando (language_id, item) VALUES (%s, %s) ON CONFLICT DO NOTHING", (language_id, item))
        else:
            conn.execute("DELETE FROM lang_cando WHERE language_id = %s AND item = %s", (language_id, item))
        return _cando(conn, language_id)
