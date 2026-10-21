"""Made-up sample data for the showcase (showcase.ps1): an empty copy of the app filled through its own API with a
believable but invented person's hobbies - no real names, accounts, places you live or anything of the user's.

Run in the e2e image on the app's network: BASE (https://web), and E2E_PASSWORD (showcase.ps1) or E2E_TOKEN, a
sign-in made for the run (sample-data.ps1: dev filled with this instead of a copy of prod).
Dates are relative to today (Brisbane), so the pages look lived-in whenever it's run.
"""
import http.cookiejar
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("BASE", "https://web")
TOKEN = os.environ.get("E2E_TOKEN")      # a sign-in made for this run (sample-data.ps1) - instead of a password
NAME = os.environ.get("SAMPLE_NAME", "Alex")   # who Home greets ("-": leave the name as it is)
TODAY = datetime.now(timezone(timedelta(hours=10))).date()     # Brisbane (no daylight saving)
tls = ssl.create_default_context()
tls.check_hostname, tls.verify_mode = False, ssl.CERT_NONE
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls),
                                     urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": ctype}
    if TOKEN:
        headers["Cookie"] = f"{os.environ.get('E2E_COOKIE', 'otc_session')}={TOKEN}"     # its name in that copy: auth.COOKIE
    req = urllib.request.Request(BASE + "/api" + path, data=data, method=method, headers=headers)
    try:
        with opener.open(req) as r:
            text = r.read()
            return json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        print(f"  ! {method} {path}: {e.code} {e.read()[:200]!r}", file=sys.stderr)
        return None


def post(path, body):
    return call("POST", path, body)


def picture(seed, w=480, h=360):
    """A made-up cover picture (PNG, no outside images): a two-colour sky, a sun, a band of hills - box-art-ish,
    different for every seed."""
    import random
    import struct
    import zlib
    r = random.Random(seed)
    top = [int(r.randint(40, 200) * 0.55 + 118 * 0.45) for _ in range(3)]     # muted: halfway to a warm grey
    low = [min(255, c + r.randint(30, 90)) for c in top]
    ground = [max(0, c - r.randint(60, 110)) for c in top]
    sx, sy, sr = r.randint(w // 4, 3 * w // 4), r.randint(h // 5, h // 2), r.randint(28, 60)
    base, amp, freq = r.uniform(0.62, 0.78) * h, r.uniform(14, 40), r.uniform(0.01, 0.03)
    import math
    rows = []
    for y in range(h):
        t = y / h
        row = bytearray([0])
        for x in range(w):
            if y > base + amp * math.sin(x * freq + seed):
                c = ground
            elif (x - sx) ** 2 + (y - sy) ** 2 < sr * sr:
                c = (250, 236, 200)
            else:
                c = [int(a + (b - a) * t) for a, b in zip(top, low)]
            row += bytes(c)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 6)
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10]) + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def photo(path, seed):
    call("PUT", path, raw=picture(seed), ctype="image/png")


def day(n):
    """n days from today (negative: ago), as YYYY-MM-DD."""
    return (TODAY + timedelta(days=n)).isoformat()


if not TOKEN:
    call("POST", "/auth/login", {"password": os.environ["E2E_PASSWORD"]})
call("PATCH", "/settings", {"default_shop": "Hobbyrama", **({} if NAME == "-" else {"your_name": NAME})})
look = call("GET", "/lookups")
cat = {c["name"]: c["id"] for c in look["categories"]}
brand = {b["name"]: b["id"] for b in look["brands"]}

# ---------------------------------------------------------------- supplies and kits
print("supplies, kits", flush=True)
paints = [("T81701", "Acrylic XF1 Flat Black", "Flat / Matt", 2, 0), ("T81702", "Acrylic XF2 Flat White", "Flat / Matt", 1, 0),
          ("T81757", "Acrylic XF57 Buff", "Flat / Matt", 1, 0), ("T81760", "Acrylic XF60 Dark Yellow", "Flat / Matt", 0, 0),
          ("T81761", "Acrylic XF61 Dark Green", "Flat / Matt", 1, 0), ("T81764", "Acrylic XF64 Red Brown", "Flat / Matt", 1, 0),
          ("T81711", "Acrylic X11 Chrome Silver", "Metallic", 1, 0), ("T81722", "Acrylic X22 Clear", "Clear", 1, 0)]
for code, name, finish, qty, reorder in paints:
    post("/supplies", {"product_code": code, "name": name, "category_id": cat["Paint"], "brand_id": brand.get("Tamiya"),
                       "paint_type": "Acrylic", "finish": finish, "size": "10ml", "qty_on_hand": qty, "reorder_at": reorder,
                       "unit_price": 4.95, "purchased_from": "Hobbyrama"})
for name, c, qty in [("Fine Surface Primer L Grey", "Primer / Surfacer", 1), ("Acrylic Thinner X-20A 46ml", "Thinner", 1),
                     ("Extra Thin Cement", "Glue / Cement", 0), ("Masking Tape 10mm", "Masking Tape", 2),
                     ("Weathering Master Set A", "Weathering", 1), ("Sanding Sponge 600", "Sanding / Abrasives", 3),
                     ("Side Cutters", "Tools", 1), ("Size 0 Detail Brush", "Brushes", 2)]:
    post("/supplies", {"name": name, "category_id": cat[c], "brand_id": brand.get("Tamiya"), "qty_on_hand": qty, "reorder_at": 0})
for name, c, pr in [("Acrylic XF62 Olive Drab", "Paint", "High"), ("Panel Line Accent Color Black", "Weathering", "Normal")]:
    post("/wishlist", {"name": name, "category_id": cat[c], "brand_id": brand.get("Tamiya"), "qty_wanted": 1, "priority": pr, "est_price": 6.5})

kits = [("1/35 M4A3E8 Sherman Easy Eight", "1/35", "In progress", "Painted", "Scale model", "SC35001"),
        ("1/48 Spitfire Mk.I", "1/48", "Finished", "Complete", "Scale model", "SC48002"),
        ("1/35 Tiger I Early Production", "1/35", "In stash", None, "Scale model", "SC35003"),
        ("1/72 P-51D Mustang", "1/72", "In stash", None, "Scale model", "SC72004"),
        ("1/24 Porsche 911 GT3", "1/24", "On hold", "Primed", "Scale model", "SC24005"),
        ("1/700 Yamato", "1/700", "Wanted", None, "Scale model", "SC70006")]
for n, (name, scale, status, stage, hobby, code) in enumerate(kits):
    post("/models", {"name": name, "scale": scale, "status": status, "stage": stage, "hobby": hobby, "brand_id": brand.get("Tamiya"),
                     "product_code": code, "price_paid": 54.0, "purchase_date": day(-40), "purchased_from": "Hobbyrama"})
    if brand.get("Tamiya"):
        photo(f"/product-photo?brand_id={brand['Tamiya']}&product_code={code}", 10 + n)
post("/models", {"name": "Space Marine Intercessors", "hobby": "Warhammer", "status": "In progress", "stage": "Primed",
                 "faction": "Ultramarines", "figures": 10, "figures_done": 4, "brand_name": "Games Workshop", "product_code": "SC40007"})
post("/models", {"name": "RX-78-2 Gundam", "hobby": "Gundam", "status": "Finished", "stage": "Complete", "grade": "HG", "scale": "1/144",
                 "brand_name": "Bandai", "product_code": "SC14408"})
look = call("GET", "/lookups")
brand = {b["name"]: b["id"] for b in look["brands"]}
for name, code, seed in [("Games Workshop", "SC40007", 30), ("Bandai", "SC14408", 31)]:
    if brand.get(name):
        photo(f"/product-photo?brand_id={brand[name]}&product_code={code}", seed)

# ---------------------------------------------------------------- board games
print("board games", flush=True)
games = [("Wingspan", "Stonemaier Games", 2019, 1, 5, 70, 9), ("Cascadia", "Flatout Games", 2021, 1, 4, 45, 8),
         ("Ticket to Ride", "Days of Wonder", 2004, 2, 5, 60, 7), ("Azul", "Next Move Games", 2017, 2, 4, 40, 8),
         ("Spirit Island", "Greater Than Games", 2017, 1, 4, 120, 10), ("Codenames", "Czech Games Edition", 2015, 2, 8, 15, 7),
         ("Everdell", "Starling Games", 2018, 1, 4, 80, 9), ("Catan", "Kosmos", 1995, 3, 4, 90, 6)]
bg = {}
for name, pub, year, lo, hi, mins, rating in games:
    g = post("/board-games", {"name": name, "publisher": pub, "year": year, "min_players": lo, "max_players": hi,
                              "play_minutes": mins, "rating": rating, "status": "Owned", "kind": "game"})
    if g:
        bg[name] = g
        photo(f"/board-games/{g['game_id']}/photo", 40 + len(bg))
post("/board-games", {"name": "Wingspan: European Expansion", "kind": "expansion", "status": "Owned",
                      "base_game_id": bg.get("Wingspan", {}).get("game_id")})
post("/board-games", {"name": "Brass: Birmingham", "status": "Wanted", "kind": "game", "year": 2018})
for n, (game, winner) in enumerate([("Wingspan", "Alex"), ("Cascadia", "Jo"), ("Azul", "Alex"), ("Spirit Island", "Everyone"),
                                     ("Codenames", "Team blue"), ("Wingspan", "Sam")]):
    post("/board-games/plays", {"game_name": game, "played_on": day(-3 - n * 5), "players": "Alex, Jo, Sam",
                                "winner": winner, "minutes": 60, "finished": True})

# ---------------------------------------------------------------- volleyball
print("volleyball", flush=True)
team = post("/volleyball/teams", {"name": "Net Results", "location": "Community sports hall", "is_default": True})
tid = team and team.get("team_id")
for n, (opp, won, lost) in enumerate([("Spike Force", 3, 1), ("Block Party", 2, 3), ("Dig Deep", 3, 0), ("Set to Win", 1, 3)]):
    post("/volleyball/games", {"played_on": day(-4 - n * 7), "kind": "Game", "team_id": tid, "opponent": opp,
                               "venue": "Community sports hall", "sets_won": won, "sets_lost": lost})
post("/volleyball/games", {"played_on": day(-2), "kind": "Training", "team_id": tid, "venue": "Community sports hall"})
for name, kind, cond in [("Indoor court shoes", "Shoes", "Good"), ("Knee pads", "Pads", "Worn"), ("Match ball", "Ball", "New")]:
    post("/gear", {"name": name, "hobby": "volleyball", "kind": kind, "condition": cond, "price_paid": 60})
call("POST", "/volleyball/coach/starter")

# ---------------------------------------------------------------- video games (by hand - no Steam account)
print("video games", flush=True)
for name, plat, done, total, hours in [("Hollow Knight", "epic", 48, 63, 61), ("Celeste", "epic", 31, 31, 34),
                                       ("Assassin's Creed Origins", "ubisoft", 40, 56, 72), ("Hades", "epic", 49, 49, 95),
                                       ("Far Cry 6", "ubisoft", 12, 50, 18), ("Outer Wilds", "epic", 9, 12, 22)]:
    g = post("/videogames/other", {"name": name, "platform": plat, "done": done, "total": total, "hours": hours})
    if g and g.get("game_id"):
        photo(f"/videogames/other/{g['game_id']}/photo", 60 + len(name))

# ---------------------------------------------------------------- chess (over the board)
print("chess", flush=True)
for n, (colour, opp, result, opening, rating) in enumerate([("white", "J. Smith", "win", "Italian Game", 1180),
                                                            ("black", "R. Lee", "draw", "Sicilian Defence", 1225),
                                                            ("white", "M. Chen", "loss", "Queen's Gambit", 1302),
                                                            ("black", "P. Kaur", "win", "French Defence", 1150),
                                                            ("white", "D. Novak", "win", "London System", 1210)]):
    post("/chess/games", {"played_on": day(-6 - n * 6), "time_class": "rapid", "colour": colour, "opp_name": opp, "result": result,
                          "opp_rating": rating, "my_rating": 1236 - n * 9, "rated": True, "event": "Club night", "opening": opening})

# ---------------------------------------------------------------- reading
print("reading", flush=True)
for title, author, pages, status, rating, genres in [
        ("Project Hail Mary", "Andy Weir", 476, "finished", 5, ["Science fiction"]),
        ("The Hobbit", "J. R. R. Tolkien", 310, "finished", 4.5, ["Fantasy"]),
        ("Atomic Habits", "James Clear", 320, "reading", None, ["Self-help"]),
        ("Dune", "Frank Herbert", 612, "owned", None, ["Science fiction"]),
        ("The Name of the Wind", "Patrick Rothfuss", 662, "want", None, ["Fantasy"]),
        ("Educated", "Tara Westover", 352, "finished", 4, ["Memoir"]),
        ("Red Rising", "Pierce Brown", 382, "finished", 4.5, ["Science fiction"])]:
    post("/reading/books", {"title": title, "author": author, "pages": pages, "status": status, "rating": rating, "genres": genres,
                            "format": "paper"})

# ---------------------------------------------------------------- hiking (two GPX recordings + one by hand)
print("hiking", flush=True)


def gpx(name, days_ago, lat0, lon0, climb):
    import time as _t
    start = _t.time() - days_ago * 86400 - 5 * 3600
    stamp = lambda s: _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(start + s))
    pts = "".join(f'<trkpt lat="{lat0 + i * 0.0011:.6f}" lon="{lon0 + (i % 7) * 0.0004:.6f}"><ele>{120 + (climb * min(i, 40 - i) // 20)}</ele>'
                  f'<time>{stamp(i * 75)}</time></trkpt>' for i in range(41))
    return (f'<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="AllTrails" xmlns="http://www.topografix.com/GPX/1/1">'
            f'<metadata><name>{name}</name></metadata><trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>').encode()


call("POST", "/hiking/import?filename=ridge.gpx", raw=gpx("Ridge Lookout Loop", 9, -27.40, 152.90, 280), ctype="application/gpx+xml")
call("POST", "/hiking/import?filename=falls.gpx", raw=gpx("Hidden Falls Track", 23, -28.20, 153.10, 190), ctype="application/gpx+xml")
post("/hiking/hikes", {"name": "Coastal Headland Walk", "hiked_on": day(-40), "distance_km": 7.4, "moving_min": 125, "ascent_m": 160,
                       "difficulty": "Moderate", "rating": 4, "weather": "Sunny, light breeze"})
for name, kind in [("Day pack 24L", "Pack"), ("Trail runners", "Shoes"), ("Trekking poles", "Poles")]:
    post("/gear", {"name": name, "hobby": "hiking", "kind": kind, "condition": "Good"})

# ---------------------------------------------------------------- gardening
print("gardening", flush=True)
space = post("/garden/spaces", {"name": "Balcony", "kind": "Balcony", "width_cm": 300, "depth_cm": 120, "facing": "N", "sun_hours": 5})
guides = {g["name"]: g["guide_id"] for g in ((call("GET", "/garden/guides") or {}).get("guides") or [])}
if space:
    sid = space["space_id"]
    for name, x, w, plant in [("Herb trough", 10, 80, "Basil"), ("Tomato pot", 110, 40, "Tomato (cherry)"),
                              ("Chilli pot", 170, 35, "Chilli"), ("Strawberry pot", 225, 40, "Strawberry")]:
        c = post("/garden/containers", {"space_id": sid, "name": name, "kind": "Pot", "x_cm": x, "y_cm": 20, "width_cm": w,
                                        "depth_cm": 35, "volume_l": 20})
        gid = next((v for k, v in guides.items() if k.lower().startswith(plant.lower().split(" (")[0])), None)
        if c:
            post("/garden/plantings", {"container_id": c["container_id"], "guide_id": gid, "name": None if gid else plant,
                                       "started_on": day(-45), "stage": "Growing", "quantity": 2,
                                       "last_watered_on": day(-1), "water_every_days": 2})

# ---------------------------------------------------------------- precision shooting
print("shooting", flush=True)
rng = post("/shooting/ranges", {"name": "Valley Rifle Range", "kind": "Club range", "distances": "50, 100, 300", "counts_for_club": True})
rifle = post("/shooting/rifles", {"name": "Rimfire trainer", "make": "CZ", "model": "457", "calibre": ".22 LR", "kind": "Rimfire",
                                  "scope_unit": "MIL", "zero_m": 50})
ammo = post("/shooting/ammo", {"name": "Match 40gr", "brand": "Eley", "calibre": ".22 LR", "bullet_gr": 40, "box_size": 50,
                               "box_price": 12.5, "rounds_bought": 500, "velocity_ms": 330})
if rng and rifle and ammo:
    for n, size in enumerate([22, 18, 15]):
        post("/shooting/sessions", {"shot_on": day(-5 - n * 14), "kind": "Practice", "range_id": rng["range_id"],
                                    "rifle_id": rifle["rifle_id"], "ammo_id": ammo["ammo_id"], "rounds": 60, "temp_c": 24,
                                    "groups": [{"distance": 50, "shots": 5, "size_mm": size}, {"distance": 100, "shots": 5, "size_mm": size * 2.1}]})

# ---------------------------------------------------------------- travel
print("travel", flush=True)
trip = post("/travel/trips", {"name": "Japan in spring", "kind": "Overseas", "status": "Planned", "start_date": day(45),
                              "end_date": day(59), "destination": "Tokyo and Kyoto", "countries": ["JP"], "budget": 6000})
post("/travel/trips", {"name": "Tasmania road trip", "kind": "Road trip", "status": "Planned", "start_date": day(-120), "end_date": day(-110),
                       "destination": "Hobart", "countries": ["AU"], "rating": 5})
for name, kind, country, lat, lon, status in [("Fushimi Inari", "Sight", "JP", 34.9671, 135.7727, "Planned"),
                                              ("Cradle Mountain", "Nature", "AU", -41.6848, 145.9516, "Been"),
                                              ("Banff", "Nature", "CA", 51.1784, -115.5708, "Want"),
                                              ("Milford Sound", "Nature", "NZ", -44.6414, 167.8974, "Want")]:
    post("/travel/places", {"name": name, "kind": kind, "country": country, "lat": lat, "lon": lon, "status": status,
                            "trip_id": trip["trip_id"] if trip and country == "JP" else None})
post("/travel/packing-lists", {"name": "Overseas basics", "items": [
    {"name": n, "grp": g} for n, g in [("Passport", "Documents"), ("Rail pass", "Documents"), ("Rain jacket", "Clothes"),
                                       ("Power adapter", "Tech"), ("Camera", "Tech"), ("Sunscreen", "Toiletries")]]})

# ---------------------------------------------------------------- goals, to-dos, calendar, journal
print("goals, to-dos, calendar, journal", flush=True)
# Goals that count themselves from the hobbies, one you update, habits, and a 3-year goal with a year's goal inside it
outdoors = post("/goals", {"title": "Get outdoors more", "timeframe": "three_years", "why": "Weekends outside, not on the couch."})
for title, source, target in [("Read 24 books", "books_finished", 24), ("Hike 300 km", "km_hiked", 300),
                              ("Reach 1400 at the club", "club_rating", 1400), ("Finish three kits this year", "kits_finished", 3)]:
    post("/goals", {"title": title, "source": source, "target_value": target, "timeframe": "year",
                    "parent_id": outdoors["goal_id"] if outdoors and source == "km_hiked" else None})
if outdoors:                       # a year's goal for next year inside it: Upcoming until then
    post("/goals", {"title": "Walk the Overland Track", "timeframe": "year", "period_start": TODAY.year + 1, "hobby": "hiking",
                    "parent_id": outdoors["goal_id"], "steps": ["Book the huts", "Train with a full pack"]})
post("/goals", {"title": "Play chess twice a week", "kind": "habit", "habit_times": 2, "source": "chess_games", "timeframe": "year"})
sketch = post("/goals", {"title": "Sketch twice a week", "kind": "habit", "habit_times": 2, "hobby": "models", "timeframe": "year"})
if sketch:
    for d in (-15, -13, -8, -6, -1):
        post(f"/goals/{sketch['goal_id']}/updates", {"day": day(d)})
post("/goals", {"title": "Run a marathon", "kind": "milestone", "timeframe": "three_years",
                "steps": ["Pick a race", "Sign up", "Build to 30 km long runs"]})
post("/goals", {"title": "Plan the Japan trip", "hobby": "travel", "target_date": day(40), "why": "Cherry blossom season.",
                "steps": ["Book flights", "Book the ryokan in Kyoto", "Buy a rail pass", "Pack the camera"]})
post("/goals", {"title": "Lose 3 kg before summer", "unit": "kg", "start_value": 82, "target_value": 79, "current_value": 81.2,
                "started_on": day(-40), "target_date": day(50)})
for title, due, pr, hobby in [("Prime the Sherman's tracks", 0, "high", "models"), ("Book Japan rail pass", 3, "normal", "travel"),
                              ("Re-pot the strawberries", 1, "normal", "gardening"), ("Clean the rimfire", -1, "normal", "shooting"),
                              ("Pick next book club read", 6, "normal", "reading")]:
    post("/todos", {"title": title, "due_on": day(due), "priority": pr, "hobby": hobby})
post("/todos", {"title": "Water the herbs", "due_on": day(0), "repeats": "daily", "hobby": "gardening"})
for title, hobby, d, t in [("Games night", "boardgames", 2, "19:00"), ("Volleyball - round 5", "volleyball", 4, "18:30"),
                           ("Club chess night", "chess", 6, "19:00"), ("Range day", "shooting", 9, "08:00")]:
    post("/calendar/events", {"title": title, "hobby": hobby, "starts_on": day(d), "start_time": t})
for n, (title, mood, text) in enumerate([("Weathering the Sherman", "great", "Tried a pin wash on the running gear - much better than last time."),
                                         ("Rainy Sunday", "good", "Two games of Wingspan and a long chapter of Project Hail Mary."),
                                         ("Ridge Lookout", "great", "Clear skies at the top; legs felt strong on the climb.")]):
    post("/journal", {"kind": "notes", "title": title, "mood": mood, "entry_date": day(-1 - n * 3),
                      "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]})
print("sample data done", flush=True)
