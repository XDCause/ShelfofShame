"""What you own for the other hobbies, for the Supplies page beside the model supplies (user, 2026-10-21: "make it
broad like the wishlist"): each hobby's own kit, by its own kinds.

    volleyball / hiking   gear you have (not Wanted, not Retired), by its kind (Shoes, Knee pads, Pack...)
    gardening             garden supplies and seeds you have (Have / Running low), by kind (Seeds, Fertiliser...)
    shooting              rifles in use, and ammunition you have (rounds left)

GET /api/owned -> [{hobby, kind, open, id, name, detail, status, amount, attention, photo_url}] - `open` says which
panel shows it (gear, garden, rifle, ammo). Each comes from its hobby's own list, so the numbers match there.
"""
from fastapi import APIRouter

from .db import db
from .garden_items import ITEM_SELECT
from .gear import GEAR_SELECT
from .shooting import AMMO_SELECT, RIFLE_SELECT, ammo_row, rifle_row

router = APIRouter(prefix="/api", tags=["supplies"])


def _join(*parts) -> str:
    return " · ".join(str(p) for p in parts if p not in (None, ""))


@router.get("/owned")
def owned():
    out = []
    with db() as conn:
        for g in conn.execute(GEAR_SELECT + " WHERE g.condition NOT IN ('Wanted', 'Retired') ORDER BY lower(g.name)").fetchall():
            out.append({"hobby": g["hobby"], "kind": g["kind"] or "Other", "open": "gear", "id": g["gear_id"], "name": g["name"],
                        "detail": _join(g["brand"], g["size"]), "status": g["condition"], "amount": None,
                        "attention": g["condition"] == "Needs replacing", "photo_url": g["photo_url"]})
        for i in conn.execute(ITEM_SELECT + " WHERE i.status IN ('Have', 'Running low') ORDER BY lower(i.name)").fetchall():
            out.append({"hobby": "gardening", "kind": i["kind"], "open": "garden", "id": i["item_id"], "name": i["name"],
                        "detail": _join(i["brand"], i["sow_by"] and f"sow by {i['sow_by'].strftime('%b %Y')}"),
                        "status": "Expired" if i["expired"] else i["status"], "amount": i["qty"],
                        "attention": i["status"] == "Running low" or bool(i["expired"]), "photo_url": i["photo_url"]})
        for r in conn.execute(RIFLE_SELECT + " WHERE r.status = 'In use' ORDER BY lower(r.name)").fetchall():
            r = rifle_row(r)
            out.append({"hobby": "shooting", "kind": "Rifles", "open": "rifle", "id": r["rifle_id"], "name": r["name"],
                        "detail": _join(r["make"], r["model"], r["calibre"]), "status": "Clean due" if r["clean_due"] else "In use",
                        "amount": None, "attention": r["clean_due"], "photo_url": r["photo_url"]})
        for a in conn.execute(AMMO_SELECT + " WHERE a.status = 'Have' ORDER BY lower(a.name)").fetchall():
            a = ammo_row(a)
            out.append({"hobby": "shooting", "kind": "Ammunition", "open": "ammo", "id": a["ammo_id"], "name": a["name"],
                        "detail": _join(a["brand"], a["calibre"], a["bullet_gr"] and f"{a['bullet_gr']:g} gr"),
                        "status": "Low" if a["low"] else "Have", "amount": f"{a['rounds_left']} rounds",
                        "attention": a["low"], "photo_url": a["photo_url"]})
    return out
