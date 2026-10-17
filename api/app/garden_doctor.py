"""Gardening's plant doctor: common problems of pots and balconies (72_garden_problems.sql) - what you see, why it
happens, what to do. Pick the signs you see; the problems that match most come first, and with a plant chosen,
the ones that plant usually gets.

    GET  /garden/problems                  the signs (grouped, for the chips) and every problem; with ?planting_id=
                                           each says whether it's common for that plant
    POST /garden/problems/{id}/found       "I've got this" on a plant: a Pest / Problem note on it (tagged with the
                                           problem) and a reminder to look again in the problem's recheck days
"""
import re

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .db import db, found, insert_row, tidy_text

router = APIRouter(prefix="/api", tags=["gardening"])

# What you can see, grouped as the chips show them. Every problem's signs are keys of this (a test checks).
SIGNS = [
    ("Leaves", [
        ("yellow-old", "Yellow older (lower) leaves"), ("yellow-new", "Yellow new leaves, green veins"),
        ("yellow-veins", "Yellow between the veins"), ("pale", "Pale, washed out"), ("purple", "Purple or red tinge"),
        ("brown-edges", "Brown, crispy edges or tips"), ("spots", "Spots or blotches"), ("white-powder", "White powder"),
        ("orange-pustules", "Orange or brown powdery bumps"), ("bleached", "Bleached or scorched patches"),
        ("speckles", "Pale speckles, silvery"), ("curl", "Curled or twisted"), ("holes", "Holes, chewed"),
        ("trails", "Wiggly trails inside"), ("sticky", "Sticky"), ("black-coat", "Black sooty coating"),
        ("black-leaves", "Black and limp after a cold night"), ("torn", "Torn or shredded"), ("leaf-drop", "Leaves falling"),
    ]),
    ("Bugs and critters", [
        ("bugs-green", "Tiny bugs on new growth"), ("flies-leaf", "White flies when you brush it"),
        ("flies-soil", "Tiny flies around the pot"), ("fluffy", "White fluff in leaf joints"), ("bumps", "Bumps stuck to stems"),
        ("webbing", "Fine webbing"), ("big-bugs", "Larger bugs on stems or fruit"), ("ants", "Ants"),
        ("slime", "Slime trails"), ("missing", "Seedlings or fruit gone overnight"),
    ]),
    ("Whole plant", [
        ("wilt-dry", "Wilting - mix is dry"), ("wilt-wet", "Wilting - mix is wet"), ("mushy", "Soft, dark stem base or roots"),
        ("collapse", "Seedlings falling over at the soil"), ("grey-fuzz", "Grey fuzzy mould"), ("leggy", "Tall, thin and leaning"),
        ("slow", "Slow or stunted"), ("bolting", "Shooting up to flower, bitter"),
    ]),
    ("Flowers and fruit", [
        ("flower-drop", "Flowers or buds dropping"), ("no-fruit", "Flowers but no fruit"), ("fruit-drop", "Small fruit dropping"),
        ("fruit-maggots", "Stings or maggots in fruit"), ("fruit-rot-end", "Dark sunken patch on the fruit's base"),
        ("fruit-split", "Fruit splitting"), ("fruit-rot", "Fruit rotting"), ("fruit-marks", "Pecked or marked fruit"),
    ]),
    ("Pot and mix", [
        ("soil-mould", "White mould or mushrooms on the mix"), ("crust", "White crust on mix or pot"),
        ("roots-out", "Roots out the bottom"), ("water-runs", "Water runs straight through"),
    ]),
]
SIGN_KEYS = {k for _, signs in SIGNS for k, _ in signs}
KINDS = [("Pest", "Bugs"), ("Disease", "Diseases"), ("Feeding", "Feeding"), ("Watering", "Watering"), ("Conditions", "Sun and weather")]
INDOOR = ("Indoor", "Shelf", "Grow tent", "Windowsill")
EARLY = ("Planned", "Sown", "Sprouted", "Seedling")

PROBLEM_SELECT = """SELECT problem_id, slug, name, kind, urgency, spreads, signs, looks, why, fix, prevent, plants, aliases,
       recheck_days, buy FROM garden_problems"""


def _stems(*names) -> set[str]:
    """Words of a plant's names, cut so plurals still match ("tomato" in "tomatoes", "strawberr" in "strawberries")."""
    out = set()
    for w in re.findall(r"[a-z]+", " ".join(n or "" for n in names).lower()):
        if len(w) >= 4:
            out.add(w[:-1] if w.endswith("y") else re.sub(r"(es|s)$", "", w) if len(w) > 5 else w)
    return out


def common_for(problem: dict, plant: dict | None) -> bool:
    """Does this plant usually get this problem? Its names in the problem's plant list, the guide's pest notes
    naming it, or seedlings / indoor plants when the problem is one of theirs."""
    if not plant:
        return False
    plants = (problem["plants"] or "").lower()
    if any(re.search(r"\b" + re.escape(w), plants) for w in _stems(plant["name"], plant["guide_name"])):
        return True
    pests = (plant["guide_pests"] or "").lower()
    if pests and any(a.lower() in pests for a in problem["aliases"]):
        return True
    return ((plant["stage"] in EARLY and "seedling" in plants) or (plant["space_kind"] in INDOOR and "indoor" in plants)
            or (plant["plant_kind"] == "Houseplant" and "houseplant" in plants))


def plant_for(conn, planting_id: int) -> dict:
    return found(conn.execute("""
        SELECT p.planting_id, p.name, p.stage, g.name AS guide_name, g.kind AS plant_kind, g.pests AS guide_pests, s.kind AS space_kind
        FROM garden_plantings p LEFT JOIN garden_guides g ON g.guide_id = p.guide_id
        LEFT JOIN garden_containers c ON c.container_id = p.container_id LEFT JOIN garden_spaces s ON s.space_id = c.space_id
        WHERE p.planting_id = %s""", (planting_id,)).fetchone(), "Plant")


@router.get("/garden/problems")
def list_problems(planting_id: int | None = Query(None)):
    with db() as conn:
        plant = plant_for(conn, planting_id) if planting_id else None
        problems = conn.execute(PROBLEM_SELECT + " ORDER BY problem_id").fetchall()
    for p in problems:
        p["common"] = common_for(p, plant)
    return {"signs": [{"group": g, "signs": [{"key": k, "label": label} for k, label in signs]} for g, signs in SIGNS],
            "kinds": [{"key": k, "label": label} for k, label in KINDS],
            "plant": plant and {"planting_id": plant["planting_id"], "name": plant["name"]}, "problems": problems}


class FoundIn(BaseModel):
    planting_id: int
    note: str | None = Field(None, max_length=2000)


@router.post("/garden/problems/{problem_id}/found", status_code=201)
def found_on(problem_id: int, body: FoundIn):
    """You've got this problem on a plant: a note on its timeline (tagged with the problem) and a reminder to look again."""
    with db() as conn:
        p = found(conn.execute(PROBLEM_SELECT + " WHERE problem_id = %s", (problem_id,)).fetchone(), "Problem")
        plant = plant_for(conn, body.planting_id)
        note = tidy_text({"note": body.note}, required=())["note"]
        log_id = insert_row(conn, "garden_logs", {
            "planting_id": plant["planting_id"], "kind": "Pest" if p["kind"] == "Pest" else "Problem", "tags": [p["name"][:40]],
            "text": f"{p['name']}" + (f": {note}" if note else f". First: {p['fix'][0]}" if p["fix"] else "")}, "log_id")
        due = conn.execute("SELECT current_date + %s AS d", (p["recheck_days"],)).fetchone()["d"]
        task_id = insert_row(conn, "garden_tasks", {
            "title": f"Check {plant['name']} for {p['name'].lower()} again", "planting_id": plant["planting_id"], "due_on": due,
            "notes": "\n".join(f"{i}. {step}" for i, step in enumerate(p["fix"], 1))}, "task_id")
        return {"log_id": log_id, "task_id": task_id, "due_on": due, "recheck_days": p["recheck_days"]}

