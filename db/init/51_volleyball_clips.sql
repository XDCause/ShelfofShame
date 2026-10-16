-- Clips: bookmarked parts of a volleyball video (start and end, in seconds), to play back or to make
-- a highlight video from. Highlight videos are ordinary videos whose file the app made with ffmpeg:
--   processing   NULL = done (or uploaded); 'making' = being made now; 'failed: <why>'
--   made_from    what it was made from ("3 clips from Full game from Somerville")
-- Idempotent: safe to run again.
CREATE TABLE IF NOT EXISTS volleyball_clips (
    clip_id     SERIAL PRIMARY KEY,
    video_id    INT NOT NULL REFERENCES volleyball_videos(video_id) ON DELETE CASCADE,
    title       TEXT,
    start_s     NUMERIC(9, 2) NOT NULL CHECK (start_s >= 0),
    end_s       NUMERIC(9, 2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_s > start_s)
);
CREATE INDEX IF NOT EXISTS volleyball_clips_video_idx ON volleyball_clips (video_id);

ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS processing TEXT;
ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS made_from TEXT;
