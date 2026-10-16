"""Volleyball clips and highlight videos.

    clips       bookmarked parts of a video (start, end in seconds) - saved instantly, nothing is cut;
                the browser plays one by jumping to its start and stopping at its end
    highlights  one or more clips (from any videos) made into a real new video file with ffmpeg,
                in the background: a new row in volleyball_videos (topic Highlights) is 'making'
                until the file is ready, then it plays and downloads like any other video

Making a video: every clip is cut from its source (fast seek with -ss before -i), scaled and padded
to the first clip's shape (long side at most 1920 px; phone videos can be portrait), 30 fps, stereo
48 kHz sound (silence for a clip without sound), joined with ffmpeg's concat filter and encoded as
H.264 / AAC MP4 with the index at the front (+faststart, so it starts playing straight away).
One video is made at a time, at low priority (nice), so the PC stays usable.
"""
import json
import logging
import os
import re
import secrets
import subprocess
import threading
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from pydantic import BaseModel, Field

from .db import db, found
from .volleyball import fetch_video, remove_file, video_dir

router = APIRouter(prefix="/api", tags=["volleyball"])
log = logging.getLogger("vbclips")

MAX_CLIP_SECONDS = 30 * 60
MAX_CLIPS = 40
LONG_SIDE = 1920
PROGRESS: dict[int, float] = {}          # video id -> 0..1 while it's being made
_one_at_a_time = threading.Lock()


# Times in seconds, as the video player gives them (12.345678...): kept to hundredths (hundredths()).
Seconds = Annotated[float, Field(ge=0, le=10_000_000)]


def hundredths(seconds: float) -> Decimal:
    return Decimal(str(round(seconds, 2)))


class ClipIn(BaseModel):
    title: str | None = Field(None, max_length=120)
    start: Seconds
    end: Seconds


class ClipPatch(BaseModel):
    title: str | None = Field(None, max_length=120)
    start: Seconds | None = None
    end: Seconds | None = None


class HighlightIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    clip_ids: list[int] = Field(min_length=1, max_length=MAX_CLIPS)   # in the order to play them


CLIP_SELECT = """
SELECT c.clip_id, c.video_id, c.title, c.start_s::float AS start, c.end_s::float AS "end",
       (c.end_s - c.start_s)::float AS seconds, x.title AS video_title
FROM volleyball_clips c JOIN volleyball_videos x USING (video_id)"""


def _check_times(start, end):
    if end <= start:
        raise HTTPException(422, "A clip has to end after it starts.")
    if end - start > MAX_CLIP_SECONDS:
        raise HTTPException(422, "A clip can be up to 30 minutes long.")


def _clip(conn, clip_id: int) -> dict:
    return found(conn.execute(CLIP_SELECT + " WHERE c.clip_id = %s", (clip_id,)).fetchone(), "Clip")


@router.get("/volleyball/videos/{video_id}/clips")
def list_clips(video_id: int):
    """A video's clips, in the order they happen."""
    with db() as conn:
        fetch_video(conn, video_id)
        return conn.execute(CLIP_SELECT + " WHERE c.video_id = %s ORDER BY c.start_s, c.clip_id", (video_id,)).fetchall()


@router.post("/volleyball/videos/{video_id}/clips", status_code=201)
def add_clip(video_id: int, body: ClipIn):
    start, end = hundredths(body.start), hundredths(body.end)
    _check_times(start, end)
    with db() as conn:
        video = fetch_video(conn, video_id)
        if not video["file_name"]:
            raise HTTPException(409, "Clips are for uploaded videos (not links).")
        if video["processing"]:
            raise HTTPException(409, "That video isn't ready yet.")
        clip_id = conn.execute("INSERT INTO volleyball_clips (video_id, title, start_s, end_s) VALUES (%s, %s, %s, %s) "
                               "RETURNING clip_id", (video_id, (body.title or "").strip() or None, start, end)
                               ).fetchone()["clip_id"]
        return _clip(conn, clip_id)


@router.patch("/volleyball/clips/{clip_id}")
def update_clip(clip_id: int, body: ClipPatch):
    sent = body.model_dump(exclude_unset=True)
    with db() as conn:
        clip = _clip(conn, clip_id)
        start = hundredths(sent["start"] if sent.get("start") is not None else clip["start"])
        end = hundredths(sent["end"] if sent.get("end") is not None else clip["end"])
        _check_times(start, end)
        title = ((sent["title"] or "").strip() or None) if "title" in sent else clip["title"]
        conn.execute("UPDATE volleyball_clips SET title = %s, start_s = %s, end_s = %s WHERE clip_id = %s",
                     (title, start, end, clip_id))
        return _clip(conn, clip_id)


@router.delete("/volleyball/clips/{clip_id}", status_code=204)
def delete_clip(clip_id: int):
    with db() as conn:
        found(conn.execute("DELETE FROM volleyball_clips WHERE clip_id = %s RETURNING clip_id", (clip_id,)).fetchone(), "Clip")
    return Response(status_code=204)


@router.post("/volleyball/highlights", status_code=202)
def make_highlights(body: HighlightIn, background: BackgroundTasks):
    """Start making a highlight video from clips (in the order given). Returns the new video, which
    is 'making' until its file is ready (GET /volleyball/highlights/{video_id} for how far it's got)."""
    with db() as conn:
        clips = {c["clip_id"]: c for c in conn.execute(
            CLIP_SELECT + " WHERE c.clip_id = ANY(%s)", (body.clip_ids,)).fetchall()}
        missing = [i for i in body.clip_ids if i not in clips]
        if missing:
            raise HTTPException(404, f"Clip {missing[0]} doesn't exist.")
        ordered = [clips[i] for i in body.clip_ids]
        sources = {c["video_id"] for c in ordered}
        games = {r["game_id"] for r in conn.execute("SELECT game_id FROM volleyball_videos WHERE video_id = ANY(%s)",
                                                    (list(sources),)).fetchall()}
        names = sorted({c["video_title"] for c in ordered})
        made_from = (f"{len(ordered)} clip{'s' if len(ordered) > 1 else ''} from "
                     + (names[0] if len(names) == 1 else f"{len(names)} videos"))
        video_id = conn.execute(
            "INSERT INTO volleyball_videos (title, topic, game_id, processing, made_from) "
            "VALUES (%s, 'Highlights', %s, 'making', %s) RETURNING video_id",
            (body.title.strip(), games.pop() if len(games) == 1 else None, made_from)).fetchone()["video_id"]
        video = fetch_video(conn, video_id)
    PROGRESS[video_id] = 0.0
    background.add_task(render, video_id, ordered)
    return {**video, "progress": 0.0}


@router.get("/volleyball/highlights/{video_id}")
def highlight_progress(video_id: int):
    """A highlight video being made: processing ('making' / 'failed: ...' / null when done) and progress 0-1."""
    with db() as conn:
        video = fetch_video(conn, video_id)
    return {**video, "progress": PROGRESS.get(video_id, 1.0 if not video["processing"] else 0.0)}


# ---------------------------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------------------------
def probe(path) -> dict:
    """The video's shape as shown (rotation applied) and whether it has sound."""
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError("ffprobe couldn't read the video")
    streams = json.loads(out.stdout).get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v:
        raise RuntimeError("no picture in the video")
    w, h = int(v["width"]), int(v["height"])
    rotation = int(float((v.get("tags") or {}).get("rotate", 0) or 0))
    for side in v.get("side_data_list") or []:
        if "rotation" in side:
            rotation = int(float(side["rotation"]))
    if abs(rotation) % 180 == 90:
        w, h = h, w
    return {"width": w, "height": h, "audio": any(s.get("codec_type") == "audio" for s in streams)}


def target_size(width: int, height: int) -> tuple[int, int]:
    """The first clip's shape, long side at most LONG_SIDE, even numbers (H.264 needs them)."""
    scale = min(1.0, LONG_SIDE / max(width, height))
    even = lambda n: max(2, int(n * scale) // 2 * 2)        # noqa: E731
    return even(width), even(height)


def command(inputs: list[dict], out_path, size: tuple[int, int]) -> list[str]:
    """The ffmpeg command: inputs = [{path, start, seconds, audio}] in order."""
    w, h = size
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    parts = []
    for i, c in enumerate(inputs):
        args += ["-ss", f"{c['start']:.2f}", "-t", f"{c['seconds']:.2f}", "-i", str(c["path"])]
        parts.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                     f"setsar=1,fps=30,format=yuv420p[v{i}]")
        if c["audio"]:
            parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={c['seconds']:.2f}[a{i}]")
    joined = "".join(f"[v{i}][a{i}]" for i in range(len(inputs)))
    parts.append(f"{joined}concat=n={len(inputs)}:v=1:a=1[v][a]")
    return args + ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "160k",
                   "-movflags", "+faststart", "-progress", "pipe:1", "-f", "mp4", str(out_path)]


def render(video_id: int, clips: list[dict]):
    """Make the highlight video's file (runs in the background)."""
    name = f"{video_id}-{secrets.token_hex(6)}.mp4"
    part = video_dir() / (name + ".part")
    try:
        with _one_at_a_time:
            with db() as conn:
                files = {r["video_id"]: r["file_name"] for r in conn.execute(
                    "SELECT video_id, file_name FROM volleyball_videos WHERE video_id = ANY(%s)",
                    ([c["video_id"] for c in clips],)).fetchall()}
            inputs, shapes = [], {}
            for c in clips:
                if not files.get(c["video_id"]):
                    raise RuntimeError(f"the video '{c['video_title']}' has no file any more")
                path = video_dir() / files[c["video_id"]]
                shapes.setdefault(path, probe(path))
                inputs.append({"path": path, "start": c["start"], "seconds": c["seconds"], "audio": shapes[path]["audio"]})
            first = shapes[inputs[0]["path"]]
            total = sum(c["seconds"] for c in inputs)
            proc = subprocess.Popen(command(inputs, part, target_size(first["width"], first["height"])),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    preexec_fn=(lambda: os.nice(10)) if hasattr(os, "nice") else None)
            for line in proc.stdout:
                m = re.match(r"out_time_us=(\d+)", line)
                if m and total:
                    PROGRESS[video_id] = min(0.99, int(m.group(1)) / 1e6 / total)
            err = proc.stderr.read()
            if proc.wait() != 0:
                raise RuntimeError((err.strip().splitlines() or ["ffmpeg failed"])[-1][:200])
            part.rename(video_dir() / name)
        with db() as conn:
            kept = conn.execute("UPDATE volleyball_videos SET file_name = %s, file_type = 'video/mp4', file_size = %s, "
                                "processing = NULL WHERE video_id = %s RETURNING video_id",
                                (name, (video_dir() / name).stat().st_size, video_id)).fetchone()
        if not kept:
            remove_file(name)                          # the video was deleted while it was being made
    except Exception as e:                             # noqa: BLE001 - any failure is shown on the video
        log.warning("Highlight video %s failed: %s", video_id, e)
        with db() as conn:
            conn.execute("UPDATE volleyball_videos SET processing = %s WHERE video_id = %s", (f"failed: {e}"[:300], video_id))
    finally:
        part.unlink(missing_ok=True)
        PROGRESS.pop(video_id, None)


def forget_unfinished():
    """At start-up: a video that was being made when the app stopped will never finish."""
    with db() as conn:
        conn.execute("UPDATE volleyball_videos SET processing = 'failed: the app restarted while making it' "
                     "WHERE processing = 'making'")
    for part in video_dir().glob("*.part"):
        part.unlink(missing_ok=True)
