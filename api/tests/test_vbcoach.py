"""Volleyball Coach: drills, things to fix and positions, with links and your own videos."""


def test_notes_with_links_and_videos(client):
    video = client.post("/api/volleyball/videos", json={"title": "My serve"}).json()
    fix = client.post("/api/volleyball/coach", json={
        "kind": "fix", "title": "Serves going into the net", "skill": "Serving",
        "body": "Toss is too far in front.", "links": [" https://youtu.be/abcdefghijk ", "https://youtu.be/abcdefghijk"],
        "video_ids": [video["video_id"]]}).json()
    assert (fix["status"], fix["links"]) == ("working on", ["https://youtu.be/abcdefghijk"])     # a fix starts as working on
    assert [v["title"] for v in fix["videos"]] == ["My serve"]
    drill = client.post("/api/volleyball/coach", json={"kind": "drill", "title": "Wall sets", "status": "sorted"}).json()
    assert drill["status"] is None                                                       # only fixes have a status
    sorted_ = client.patch(f"/api/volleyball/coach/{fix['note_id']}", json={"status": "sorted"}).json()
    assert sorted_["status"] == "sorted"
    assert client.patch(f"/api/volleyball/coach/{drill['note_id']}", json={"status": "sorted"}).status_code == 422
    # A drill turned into a fix starts as working on; back to a drill loses the status.
    assert client.patch(f"/api/volleyball/coach/{drill['note_id']}", json={"kind": "fix"}).json()["status"] == "working on"
    assert client.patch(f"/api/volleyball/coach/{drill['note_id']}", json={"kind": "drill"}).json()["status"] is None
    assert client.post("/api/volleyball/coach", json={"kind": "drill", "title": "X", "links": ["javascript:alert(1)"]}).status_code == 422
    assert client.post("/api/volleyball/coach", json={"kind": "tip", "title": "X"}).status_code == 422
    pinned = client.patch(f"/api/volleyball/coach/{drill['note_id']}", json={"pinned": True}).json()
    notes = client.get("/api/volleyball/coach").json()
    assert notes["notes"][0]["note_id"] == pinned["note_id"] and "Setter" in notes["positions"]
    # A video deleted: the note just doesn't list it any more.
    client.delete(f"/api/volleyball/videos/{video['video_id']}")
    assert client.get("/api/volleyball/coach").json()["notes"][1]["videos"] == []
    assert client.delete(f"/api/volleyball/coach/{fix['note_id']}").status_code == 204


def test_the_starter_set_once(client):
    r = client.post("/api/volleyball/coach/starter")
    assert r.status_code == 201 and r.json()["has_starter"]
    kinds = [n["kind"] for n in r.json()["notes"]]
    assert kinds.count("position") == 6 and kinds.count("drill") >= 6
    assert client.post("/api/volleyball/coach/starter").status_code == 409
