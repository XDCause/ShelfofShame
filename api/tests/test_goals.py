"""Goals: details, steps, a number to track, progress notes, and the activity feed."""


def test_goal_with_steps_and_progress(client):
    goal = client.post("/api/goals", json={
        "title": " Finish the shelf of shame ", "hobby": "models", "why": "Too many boxes.", "details": "One kit a month.",
        "target_date": "2027-06-30", "steps": ["Finish the Zero", " ", "Finish the Sherman", "Finish the P-40E"]}).json()
    assert goal["title"] == "Finish the shelf of shame" and goal["status"] == "active"
    assert [s["text"] for s in goal["steps"]] == ["Finish the Zero", "Finish the Sherman", "Finish the P-40E"]
    assert (goal["progress"], goal["next_step"]) == (0, "Finish the Zero")
    assert goal["days_left"] is not None
    first = goal["steps"][0]["step_id"]
    g = client.patch(f"/api/goal-steps/{first}", json={"done": True}).json()
    assert g["steps_done"] == 1 and abs(g["progress"] - 1 / 3) < 1e-9 and g["next_step"] == "Finish the Sherman"
    assert g["steps"][0]["done_on"] is not None
    g = client.patch(f"/api/goal-steps/{first}", json={"done": False}).json()
    assert g["steps"][0]["done_on"] is None
    g = client.post(f"/api/goals/{goal['goal_id']}/steps", json={"text": "Paint the Gundam"}).json()
    ids = [s["step_id"] for s in g["steps"]]
    g = client.put(f"/api/goals/{goal['goal_id']}/steps/order", json={"step_ids": ids[::-1]}).json()
    assert g["steps"][0]["text"] == "Paint the Gundam"
    assert client.put(f"/api/goals/{goal['goal_id']}/steps/order", json={"step_ids": ids[:2]}).status_code == 422
    g = client.delete(f"/api/goal-steps/{ids[0]}").json()
    assert g["steps_total"] == 3
    assert client.post("/api/goals", json={"title": "X", "hobby": "knitting"}).status_code == 422
    assert client.post("/api/goals", json={"title": " "}).status_code == 422


def test_number_goal_and_notes(client):
    goal = client.post("/api/goals", json={"title": "Read 30 books", "hobby": "reading", "unit": "books",
                                           "start_value": 0, "target_value": 30}).json()
    assert goal["progress"] is None                        # no current value yet, no steps
    gid = goal["goal_id"]
    g = client.post(f"/api/goals/{gid}/updates", json={"day": "2026-10-01", "value": 6, "text": "Good month"}).json()
    assert g["current_value"] == 6 and abs(g["progress"] - 0.2) < 1e-9
    g = client.post(f"/api/goals/{gid}/updates", json={"day": "2026-09-01", "value": 3}).json()
    assert g["current_value"] == 6                         # an older note doesn't move it back
    g = client.post(f"/api/goals/{gid}/updates", json={"day": "2026-10-10", "text": "Halfway through Dune"}).json()
    assert [u["day"] for u in g["updates"]] == ["2026-10-10", "2026-10-01", "2026-09-01"]
    assert client.post(f"/api/goals/{gid}/updates", json={"text": "  "}).status_code == 422
    newest = g["updates"][1]["update_id"]
    g = client.delete(f"/api/goal-updates/{newest}").json()
    assert g["current_value"] == 3                         # back to the latest one left
    # Past the target counts as all the way.
    assert client.patch(f"/api/goals/{gid}", json={"current_value": 45}).json()["progress"] == 1
    # Going down (lose 5 kg: 80 -> 75): halfway at 77.5.
    kg = client.post("/api/goals", json={"title": "Lose 5 kg", "unit": "kg", "start_value": 80, "target_value": 75,
                                         "current_value": 77.5}).json()
    assert kg["progress"] == 0.5


def test_status_and_order_and_activity(client):
    a = client.post("/api/goals", json={"title": "Later", "target_date": "2027-12-01"}).json()
    b = client.post("/api/goals", json={"title": "Sooner", "target_date": "2027-01-01"}).json()
    c = client.post("/api/goals", json={"title": "Pinned one", "pinned": True}).json()
    done = client.patch(f"/api/goals/{a['goal_id']}", json={"status": "done"}).json()
    assert done["done_on"] is not None and done["days_left"] is None
    listed = client.get("/api/goals").json()
    assert [g["title"] for g in listed["goals"]] == ["Pinned one", "Sooner", "Later"]
    assert listed["counts"] == {"active": 2, "paused": 0, "done": 1, "dropped": 0}
    assert [g["title"] for g in client.get("/api/goals?status=done").json()["goals"]] == ["Later"]
    client.post(f"/api/goals/{b['goal_id']}/updates", json={"text": "Booked lessons"})
    feed = client.get("/api/activity?limit=50").json()
    assert {(r["verb"], r["title"]) for r in feed if r["kind"] == "goal"} == {("Reached", "Later"), ("Progress on", "Sooner")}
    back = client.patch(f"/api/goals/{a['goal_id']}", json={"status": "active"}).json()
    assert back["done_on"] is None
    assert client.delete(f"/api/goals/{c['goal_id']}").status_code == 204
    assert client.get(f"/api/goals/{c['goal_id']}").status_code == 404


def test_year_and_three_year_goals(client):
    this_year = client.get("/api/goals").json()["this_year"]
    year = client.post("/api/goals", json={"title": "Read 30 books", "timeframe": "year"}).json()
    assert (year["period_start"], year["target_date"]) == (this_year, f"{this_year}-12-31")
    three = client.post("/api/goals", json={"title": "Build a car", "timeframe": "three_years", "period_start": 2027}).json()
    assert three["target_date"] == "2029-12-31"
    # Moving it to next year moves the target day along; a day you picked yourself stays.
    moved = client.patch(f"/api/goals/{year['goal_id']}", json={"period_start": this_year + 1}).json()
    assert moved["target_date"] == f"{this_year + 1}-12-31"
    client.patch(f"/api/goals/{three['goal_id']}", json={"target_date": "2028-06-30"})
    kept = client.patch(f"/api/goals/{three['goal_id']}", json={"timeframe": "year"}).json()
    assert (kept["timeframe"], kept["period_start"], kept["target_date"]) == ("year", 2027, "2028-06-30")
    plain = client.patch(f"/api/goals/{three['goal_id']}", json={"timeframe": None}).json()
    assert (plain["timeframe"], plain["period_start"]) == (None, None)
    assert client.post("/api/goals", json={"title": "X", "timeframe": "decade"}).status_code == 422
    assert client.post("/api/goals", json={"title": "No time", "target_date": None}).json()["target_date"] is None
