-- Volleyball videos are uploaded, not links (2026-10-15).
--
-- A video file is kept on disk (the media folder next to the app, /media in the api container),
-- not in the database: phone videos are hundreds of megabytes. The row keeps what the file is:
--   file_name      its name in media/videos (made up by the app: "<video_id>-<random>.mp4")
--   file_type      video/mp4, video/quicktime (iPhone), video/webm...
--   file_size      bytes
--   original_name  what it was called on your phone
-- A link (url) still works for older rows, so url can now be empty.
--
-- Idempotent: safe on a fresh database (docker init) and on an existing one (migrate.ps1).

ALTER TABLE volleyball_videos ALTER COLUMN url DROP NOT NULL;
ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS file_name TEXT CHECK (file_name ~ '^[0-9]+-[a-z0-9]+\.[a-z0-9]{2,5}$');
ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS file_type TEXT;
ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS file_size BIGINT CHECK (file_size > 0);
ALTER TABLE volleyball_videos ADD COLUMN IF NOT EXISTS original_name TEXT;
