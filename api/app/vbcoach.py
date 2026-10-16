"""Volleyball Coach: your own notes - drills, things to fix (issues you're having, with tips) and
positions - each with web links (YouTube...) and your own uploaded videos.

    GET    /volleyball/coach              every note: pinned, then things you're working on, then the rest
    POST   /volleyball/coach              a new note
    PATCH  /volleyball/coach/{id}         change one (a fix: 'working on' <-> 'sorted')
    DELETE /volleyball/coach/{id}
    POST   /volleyball/coach/starter      add the starter set (common drills + the six positions), once

The starter set is written for this app (no copied text) and has no video links: every note gets a
"Find videos" search link in the page instead, so nothing points at a video that might vanish.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text, update_row

router = APIRouter(prefix="/api", tags=["volleyball"])

Kind = Literal["drill", "fix", "position"]
Status = Literal["working on", "sorted"]
SKILLS = ["Serving", "Passing", "Setting", "Attacking", "Blocking", "Defence", "Footwork", "Serve receive", "Fitness"]
POSITIONS = ["Setter", "Outside hitter", "Opposite", "Middle blocker", "Libero", "Defensive specialist"]


class NoteIn(BaseModel):
    kind: Kind
    title: str = Field(min_length=1, max_length=200)
    skill: str | None = Field(None, max_length=60)
    position: str | None = Field(None, max_length=60)
    body: str | None = Field(None, max_length=20000)
    status: Status | None = None
    links: list[str] = Field(default_factory=list, max_length=20)
    video_ids: list[int] = Field(default_factory=list, max_length=20)
    pinned: bool = False


class NotePatch(BaseModel):
    kind: Kind | None = None
    title: str | None = Field(None, min_length=1, max_length=200)
    skill: str | None = Field(None, max_length=60)
    position: str | None = Field(None, max_length=60)
    body: str | None = Field(None, max_length=20000)
    status: Status | None = None
    links: list[str] | None = Field(None, max_length=20)
    video_ids: list[int] | None = Field(None, max_length=20)
    pinned: bool | None = None


# Each note with its own videos' titles and addresses (so the page can show and play them).
NOTE_SELECT = """
SELECT n.*, COALESCE((SELECT json_agg(json_build_object('video_id', x.video_id, 'title', x.title, 'file_url',
           CASE WHEN x.file_name IS NOT NULL THEN '/api/volleyball/videos/' || x.video_id || '/file?v=' || x.file_name END,
           'url', x.url) ORDER BY array_position(n.video_ids, x.video_id))
         FROM volleyball_videos x WHERE x.video_id = ANY(n.video_ids)), '[]') AS videos
FROM volleyball_coach n"""


def tidy(data: dict, kind: str | None) -> dict:
    """Links must be web addresses; a fix always has a status (working on, unless you say), others none."""
    if "links" in data and data["links"] is not None:
        links = [link.strip() for link in data["links"] if link and link.strip()]
        bad = [link for link in links if not link.lower().startswith(("http://", "https://"))]
        if bad:
            raise HTTPException(422, f"Links must start with http:// or https:// ({bad[0]}).")
        data["links"] = list(dict.fromkeys(links))
    if "video_ids" in data and data["video_ids"] is not None:
        data["video_ids"] = list(dict.fromkeys(data["video_ids"]))
    if kind == "fix":
        data["status"] = data.get("status") or "working on"
    elif kind is not None:
        data["status"] = None
    return data


def fetch(conn, note_id: int) -> dict:
    return found(conn.execute(NOTE_SELECT + " WHERE n.note_id = %s", (note_id,)).fetchone(), "Note")


@router.get("/volleyball/coach")
def list_notes():
    with db() as conn:
        notes = conn.execute(NOTE_SELECT + """ ORDER BY n.pinned DESC, n.status = 'working on' DESC NULLS LAST,
                             array_position(ARRAY['fix', 'drill', 'position'], n.kind), lower(n.title)""").fetchall()
        return {"notes": notes, "skills": SKILLS, "positions": POSITIONS,
                "has_starter": any(n["starter"] for n in notes)}


@router.post("/volleyball/coach", status_code=201)
def add_note(body: NoteIn):
    data = tidy(tidy_text(body.model_dump(), required=("title",)), body.kind)
    with db() as conn:
        return fetch(conn, insert_row(conn, "volleyball_coach", data, "note_id"))


@router.patch("/volleyball/coach/{note_id}")
def update_note(note_id: int, body: NotePatch):
    data = tidy_text(body.model_dump(exclude_unset=True), required=("title",))
    for field in ("kind", "links", "video_ids", "pinned"):
        if field in data and data[field] is None:
            raise HTTPException(422, f"{field} can't be empty.")
    with db() as conn:
        note = fetch(conn, note_id)
        kind = data.get("kind", note["kind"])
        if "status" in data and kind != "fix":
            raise HTTPException(422, "Only things to fix have a status.")
        if "kind" in data or "status" in data:
            data.setdefault("status", note["status"])
            data = tidy(data, kind)
        else:
            data = tidy(data, None)
        update_row(conn, "volleyball_coach", "note_id", note_id, data)
        return fetch(conn, note_id)


@router.delete("/volleyball/coach/{note_id}", status_code=204)
def delete_note(note_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM volleyball_coach WHERE note_id = %s RETURNING note_id", (note_id,)).fetchone(), "Note")
    return Response(status_code=204)


@router.post("/volleyball/coach/starter", status_code=201)
def add_starter():
    """The starter set: common drills and the six positions. Only once (409 if it's there already)."""
    with db() as conn:
        if conn.execute("SELECT 1 FROM volleyball_coach WHERE starter LIMIT 1").fetchone():
            raise HTTPException(409, "The starter set is already in your notes.")
        for kind, title, skill, position, text in STARTER:
            insert_row(conn, "volleyball_coach", {"kind": kind, "title": title, "skill": skill, "position": position,
                                                  "body": text, "starter": True}, "note_id")
    return list_notes()                    # after the save (list_notes uses its own connection)


# (kind, title, skill, position, how)
STARTER = [
    ("drill", "Pepper", "Passing", None,
     "Two players, one ball: pass, set, hit - over and over, controlled.\n"
     "- Keep it going: aim every touch to your partner's chest.\n"
     "- The 'hit' is a controlled down-ball, not a spike.\n"
     "- Count your rally; try to beat it next time."),
    ("drill", "Butterfly passing", "Passing", None,
     "Three lines: a server, a passer, a target at the setter's spot. Serve, pass to the target, then everyone "
     "follows their ball to the next line.\n"
     "- Platform angled to the target before the ball arrives.\n"
     "- Feet still when you pass; move first, then pass.\n"
     "- Score it: 3 = perfect to the target, 0 = shank."),
    ("drill", "Serving to zones", "Serving", None,
     "Put towels or cones in the six zones. Serve 10 to a called zone, count the hits.\n"
     "- Same toss every time: most errors start with the toss.\n"
     "- Follow through to your target.\n"
     "- Finish with pressure: you must land 3 in a row before you stop."),
    ("drill", "Wall sets", "Setting", None,
     "Stand close to a wall and set against it continuously, then step back.\n"
     "- Hands up early, ball meets you at the forehead, thumbs and index fingers make a window.\n"
     "- Extend your arms and legs together; finish pointing at the target.\n"
     "- Try 50 in a row without the ball spinning."),
    ("drill", "Approach footwork", "Attacking", None,
     "Practise the approach without a ball: (right-handed) left-right-left, or the 4-step right-left-right-left.\n"
     "- Slow first step, fast last two; the last two are the 'step-close'.\n"
     "- Both arms swing back on the penultimate step, then up together.\n"
     "- Jump up, not forward: land where you took off."),
    ("drill", "Block footwork at the net", "Blocking", None,
     "Shuffle and crossover steps along the net, jumping at each antenna, hands over.\n"
     "- Hands stay up at shoulder height while you move.\n"
     "- Press over the net, thumbs up, seal it - don't swing at the ball.\n"
     "- Land on two feet, ready to turn and play."),
    ("drill", "Dig to target", "Defence", None,
     "A partner hits down-balls at you from a box; dig them up to a target at the setter's spot.\n"
     "- Low and balanced before the hit, weight forward.\n"
     "- Absorb hard hits: give with the platform, don't swing.\n"
     "- High and to the middle is a good dig."),
    ("position", "Setter", "Setting", "Setter",
     "Runs the offence: usually takes the second ball and sets the hitters.\n"
     "- Gets to the target spot (right of middle, near the net) on every play.\n"
     "- Reads the pass and the block, chooses who to set.\n"
     "- Talks a lot: calls plays, tells hitters what's coming."),
    ("position", "Outside hitter", "Attacking", "Outside hitter",
     "Attacks from the left side; also passes serve and plays defence - the all-rounder.\n"
     "- Hits high sets and out-of-system balls, so needs a range of shots.\n"
     "- Usually a main passer in serve receive.\n"
     "- Blocks the other team's right side."),
    ("position", "Opposite", "Attacking", "Opposite",
     "Plays opposite the setter: attacks from the right side, often from the back row too.\n"
     "- Big blocking job against the other team's outside hitter.\n"
     "- Usually doesn't pass serve.\n"
     "- Sets when the setter has to take the first ball."),
    ("position", "Middle blocker", "Blocking", "Middle blocker",
     "In the middle of the net: blocks across the whole net and hits quick sets.\n"
     "- Reads the setter and moves to block every attack.\n"
     "- Fast attacks (quicks) keep the other team's middle honest.\n"
     "- Often swapped out by the libero in the back row."),
    ("position", "Libero", "Serve receive", "Libero",
     "The back-row defence specialist, in a different coloured shirt.\n"
     "- Passes serve and digs; can't attack above the net or block.\n"
     "- Can sub in for any back-row player without counting as a sub.\n"
     "- If they set from in front of the 3 m line, it must be a dig (bump) set to attack it."),
    ("position", "Defensive specialist", "Defence", "Defensive specialist",
     "A back-row sub for passing and defence (like a libero, but with normal sub rules).\n"
     "- Comes in for a front-row player when they rotate to the back.\n"
     "- Serves, passes, digs.\n"
     "- Can attack from behind the 3 m line."),
]
