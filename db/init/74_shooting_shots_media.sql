-- Precision shooting, more (2026-10-19): every shot in a group, and a session's photos and videos. Idempotent.
--   shooting_shots  one shot: where it landed from the aim point (mm; right and up are positive), its score / X,
--                   its velocity, and whether it was a called flyer (left out of the group's size and centre).
--                   When a group has shots, its size, centre, shot count, velocities and score are worked out
--                   from them (shooting_sessions.recompute).
--   shooting_media  a session's photos (kept here, shrunk by the browser first) and videos (files in the media
--                   folder's videos/, like volleyball's - the nightly backup copies them), optionally of one group.
BEGIN;

CREATE TABLE IF NOT EXISTS shooting_shots (
    shot_id     serial PRIMARY KEY,
    group_id    integer NOT NULL REFERENCES shooting_groups ON DELETE CASCADE,
    n           integer NOT NULL CHECK (n BETWEEN 1 AND 1000),        -- the order it was fired
    x_mm        numeric(7, 1),                                        -- right of the aim point (left = minus)
    y_mm        numeric(7, 1),                                        -- above it (below = minus)
    score       numeric(5, 1) CHECK (score >= 0),
    is_x        boolean NOT NULL DEFAULT false,
    velocity    numeric(6, 1) CHECK (velocity > 0 AND velocity < 3000),
    flyer       boolean NOT NULL DEFAULT false,                       -- a called flyer: not counted in the group
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK ((x_mm IS NULL) = (y_mm IS NULL))
);
CREATE INDEX IF NOT EXISTS shooting_shots_group_idx ON shooting_shots (group_id, n);

CREATE TABLE IF NOT EXISTS shooting_media (
    media_id       serial PRIMARY KEY,
    session_id     integer NOT NULL REFERENCES shooting_sessions ON DELETE CASCADE,
    group_id       integer REFERENCES shooting_groups ON DELETE SET NULL,
    kind           text NOT NULL CHECK (kind IN ('photo', 'video')),
    caption        text,
    photo          bytea,
    photo_type     text,
    file_name      text,             -- a video: its file in <media>/videos
    file_type      text,
    file_size      bigint,
    original_name  text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind = 'photo') = (photo IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS shooting_media_session_idx ON shooting_media (session_id, created_at);

COMMIT;
