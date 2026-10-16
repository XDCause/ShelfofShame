"""Volleyball clips and highlight videos, made with the real ffmpeg on tiny generated videos."""
import json
import subprocess

import pytest

from app import vbclips
from app.db import db


def make_video(tmp_path, client, title, size="320x240", sound=True, seconds=4):
    """A video row with a real little file: a test pattern (and a tone)."""
    video = client.post("/api/volleyball/videos", json={"title": title}).json()
    name = f"{video['video_id']}-abc123.mp4"
    args = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=30:duration={seconds}"]
    if sound:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"] + (["-c:a", "aac"] if sound else []) + \
        ["-shortest", str(tmp_path / "videos" / name)]
    (tmp_path / "videos").mkdir(exist_ok=True)
    subprocess.run(args, check=True, timeout=60)
    with db() as conn:
        conn.execute("UPDATE volleyball_videos SET file_name = %s, file_type = 'video/mp4', file_size = 1 WHERE video_id = %s",
                     (name, video["video_id"]))
    return video["video_id"]


def info(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.fixture
def media(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path))
    return tmp_path


def test_clips_are_bookmarks(client, media):
    game = make_video(media, client, "Full game")
    clip = client.post(f"/api/volleyball/videos/{game}/clips", json={"title": " Kill from the 4 ", "start": 1.5, "end": 3}).json()
    assert (clip["title"], clip["start"], clip["end"], clip["seconds"]) == ("Kill from the 4", 1.5, 3.0, 1.5)
    client.post(f"/api/volleyball/videos/{game}/clips", json={"start": 0.2, "end": 1})
    # The player's times have many decimals: kept to hundredths.
    odd = client.post(f"/api/volleyball/videos/{game}/clips", json={"start": 2.123456789, "end": 2.987654321})
    assert odd.status_code == 201 and (odd.json()["start"], odd.json()["end"]) == (2.12, 2.99)
    client.delete(f"/api/volleyball/clips/{odd.json()['clip_id']}")
    assert [c["start"] for c in client.get(f"/api/volleyball/videos/{game}/clips").json()] == [0.2, 1.5]   # in time order
    assert client.post(f"/api/volleyball/videos/{game}/clips", json={"start": 3, "end": 2}).status_code == 422
    assert client.post(f"/api/volleyball/videos/{game}/clips", json={"start": 0, "end": 4000}).status_code == 422
    moved = client.patch(f"/api/volleyball/clips/{clip['clip_id']}", json={"end": 3.5, "title": ""}).json()
    assert (moved["start"], moved["end"], moved["title"]) == (1.5, 3.5, None)
    assert client.patch(f"/api/volleyball/clips/{clip['clip_id']}", json={"start": 3.6}).status_code == 422
    link = client.post("/api/volleyball/videos", json={"title": "YouTube", "url": "https://youtu.be/x"}).json()
    assert client.post(f"/api/volleyball/videos/{link['video_id']}/clips", json={"start": 0, "end": 1}).status_code == 409
    assert client.delete(f"/api/volleyball/clips/{clip['clip_id']}").status_code == 204
    # Deleting the video deletes its clips.
    client.delete(f"/api/volleyball/videos/{game}")
    with db() as conn:
        assert conn.execute("SELECT count(*) AS n FROM volleyball_clips WHERE video_id = %s", (game,)).fetchone()["n"] == 0


def test_a_highlight_video_from_clips_of_two_videos(client, media):
    game = make_video(media, client, "Full game", size="640x360")
    phone = make_video(media, client, "Upright, no sound", size="180x320", sound=False, seconds=3)
    a = client.post(f"/api/volleyball/videos/{game}/clips", json={"title": "Ace", "start": 0.5, "end": 2}).json()
    b = client.post(f"/api/volleyball/videos/{phone}/clips", json={"title": "Dig", "start": 1, "end": 2}).json()
    made = client.post("/api/volleyball/highlights", json={"title": "Best of week 1", "clip_ids": [b["clip_id"], a["clip_id"]]})
    assert made.status_code == 202
    video = made.json()
    assert (video["topic"], video["made_from"], video["edit"]) == ("Highlights", "2 clips from 2 videos", "edited")
    assert client.get("/api/volleyball/videos").json()[-1]["edit"] == "raw"          # uploads are raw
    # (The test client runs the background job before handing the answer back: it's made now.)
    done = client.get(f"/api/volleyball/highlights/{video['video_id']}").json()
    assert (done["processing"], done["progress"]) == (None, 1.0) and done["file_url"]
    meta = info(media / "videos" / done["file_name"])
    pic = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert (pic["codec_name"], pic["width"], pic["height"]) == ("h264", 180, 320)   # the first clip's shape (upright)
    assert any(s["codec_type"] == "audio" for s in meta["streams"])                 # silence where there was none
    assert abs(float(meta["format"]["duration"]) - 2.5) < 0.3                       # 1 s + 1.5 s
    # It plays and downloads like any other video.
    r = client.get(f"/api/volleyball/videos/{video['video_id']}/file?download=true")
    assert r.status_code == 200 and r.headers["content-disposition"] == "attachment; filename*=utf-8''Best%20of%20week%201.mp4"
    assert list((media / "videos").glob("*.part")) == []
    assert client.post("/api/volleyball/highlights", json={"title": "X", "clip_ids": [999999]}).status_code == 404


def test_a_failed_highlight_says_why(client, media):
    game = make_video(media, client, "Full game")
    clip = client.post(f"/api/volleyball/videos/{game}/clips", json={"start": 0, "end": 1}).json()
    (media / "videos" / f"{game}-abc123.mp4").write_bytes(b"not a video any more")
    video = client.post("/api/volleyball/highlights", json={"title": "Broken", "clip_ids": [clip["clip_id"]]}).json()
    done = client.get(f"/api/volleyball/highlights/{video['video_id']}").json()
    assert done["processing"].startswith("failed:") and not done["file_name"]


def test_unfinished_ones_are_marked_failed_at_start_up(client, media):
    with db() as conn:
        conn.execute("INSERT INTO volleyball_videos (title, processing) VALUES ('Half made', 'making')")
    (media / "videos").mkdir(exist_ok=True)
    (media / "videos" / "9-abc.mp4.part").write_bytes(b"half")
    vbclips.forget_unfinished()
    with db() as conn:
        assert conn.execute("SELECT processing FROM volleyball_videos WHERE title = 'Half made'").fetchone()["processing"] \
            .startswith("failed")
    assert not (media / "videos" / "9-abc.mp4.part").exists()


def test_the_shape_of_the_result():
    assert vbclips.target_size(3840, 2160) == (1920, 1080)
    assert vbclips.target_size(1080, 1920) == (1080, 1920)
    assert vbclips.target_size(321, 241) == (320, 240)          # even numbers


def test_raw_or_edited(client):
    up = client.post("/api/volleyball/videos", json={"title": "Phone video"}).json()
    done = client.post("/api/volleyball/videos", json={"title": "Edited on the phone", "edit": "edited"}).json()
    link = client.post("/api/volleyball/videos", json={"title": "YouTube", "url": "https://youtu.be/x"}).json()
    assert (up["edit"], done["edit"], link["edit"]) == ("raw", "edited", None)
    assert client.patch(f"/api/volleyball/videos/{up['video_id']}", json={"edit": "edited"}).json()["edit"] == "edited"
    assert client.patch(f"/api/volleyball/videos/{up['video_id']}", json={"edit": "polished"}).status_code == 422
