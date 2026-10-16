"""Everything you want to buy, grouped by the shop you'd buy it from - for the Wishlist page.

    supplies     the wishlist itself (paints, glue...): your default shop (Settings; Hobbyrama)
    kits         Wanted models (Tamiya, Gundam, Warhammer...): the shop typed on the kit, else the default shop
    board games  Wanted games: Good Games
    gear         Wanted gear: the shop it was found at (Blue Sky Athletics for Way of Wade), else "No shop yet"

GET /api/wanted -> {default_shop, supplies (how many on the wishlist), shops: [{shop, items, total}]}; the
default shop comes first (the wishlist's own list sits under it on the page), "No shop yet" last.
"""
from fastapi import APIRouter

from .boardgames import GAME_SELECT
from .db import db
from .settings import get_setting
from .volleyball import GEAR_SELECT

router = APIRouter(prefix="/api", tags=["wishlist"])

BOARD_GAME_SHOP = "Good Games"
NO_SHOP = "No shop yet"


@router.get("/wanted")
def wanted():
    with db() as conn:
        default = get_setting(conn, "default_shop") or "Hobbyrama"
        supplies = conn.execute("SELECT count(*) AS n FROM wishlist WHERE NOT got_it").fetchone()["n"]
        kits = conn.execute("""
            SELECT m.model_id, m.name, m.hobby, m.scale, m.grade, m.faction, m.purchased_from, m.price_paid,
                   b.name AS brand, p.product_info_id, p.fetched_at AS photo_updated, (p.image IS NOT NULL) AS has_image,
                   p.source_url
            FROM models m LEFT JOIN brands b USING (brand_id)
            LEFT JOIN product_info p ON p.brand_id = m.brand_id AND p.product_code = m.product_code
            WHERE m.status = 'Wanted' ORDER BY lower(m.name)""").fetchall()
        games = conn.execute(GAME_SELECT + " WHERE g.status = 'Wanted' ORDER BY lower(g.name)").fetchall()
        gear = conn.execute(GEAR_SELECT + " WHERE g.condition = 'Wanted' ORDER BY lower(g.name)").fetchall()

    shops: dict[str, list] = {}
    for m in kits:
        shops.setdefault((m["purchased_from"] or "").strip() or default, []).append({
            "kind": "model", "id": m["model_id"], "name": m["name"], "label": m["hobby"] if m["hobby"] != "Scale model" else "Kit",
            "detail": " · ".join(filter(None, [m["brand"], m["grade"], m["scale"], m["faction"]])),
            "price": m["price_paid"], "product_info_id": m["product_info_id"] if m["has_image"] else None,
            "photo_updated": m["photo_updated"], "url": m["source_url"]})
    for g in games:
        shops.setdefault(BOARD_GAME_SHOP, []).append({
            "kind": "game", "id": g["game_id"], "name": g["name"], "label": "Board game",
            "detail": " · ".join(filter(None, [g["publisher"], g["kind"] != "game" and g["kind"]])),
            "price": g["shop_price"], "photo_url": g["photo_url"], "url": g["shop_url"]})
    for g in gear:
        shops.setdefault(g["shop_name"] or NO_SHOP, []).append({
            "kind": "gear", "id": g["gear_id"], "name": g["name"], "label": g["kind"] or "Gear",
            "detail": " · ".join(filter(None, [g["brand"], g["size"] and f"size {g['size']}"])),
            "price": g["shop_price"], "photo_url": g["photo_url"], "url": g["shop_url"]})
    shops.setdefault(default, [])
    order = sorted(shops, key=lambda s: (s != default, s == NO_SHOP, s.lower()))
    return {"default_shop": default, "supplies": supplies,
            "shops": [{"shop": s, "items": shops[s], "total": float(sum(i["price"] or 0 for i in shops[s]))} for s in order]}
