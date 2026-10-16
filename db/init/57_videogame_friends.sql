-- Video games: your Steam friends (from your friends list when it's public, or added by hand) and
-- how they're doing on the games you both have with achievements (read when you press Compare).
-- Personal data about other people, kept only on this PC (see BEFORE_GOING_PUBLIC.md).
-- Idempotent: safe to run again.
CREATE TABLE IF NOT EXISTS vg_friends (
    steam_id      TEXT PRIMARY KEY CHECK (steam_id ~ '^7656[0-9]{13}$'),
    name          TEXT,
    avatar_url    TEXT,
    profile_url   TEXT,
    public        BOOLEAN,                 -- their profile is public (else nothing more can be read)
    status        TEXT,                    -- Online / Offline / Away... (when public)
    playing       TEXT,                    -- the game they're in right now
    from_list     BOOLEAN NOT NULL DEFAULT false,   -- on your Steam friends list
    by_hand       BOOLEAN NOT NULL DEFAULT false,   -- added by you
    hidden        BOOLEAN NOT NULL DEFAULT false,
    seen_at       TIMESTAMPTZ,             -- name / status last read
    compared_at   TIMESTAMPTZ,
    compare_error TEXT,
    games_owned   INT
);

CREATE TABLE IF NOT EXISTS vg_friend_games (
    steam_id      TEXT NOT NULL REFERENCES vg_friends(steam_id) ON DELETE CASCADE,
    app_id        INT NOT NULL,
    playtime_minutes INT,
    done          INT,                     -- their achievements (NULL = couldn't be read)
    total         INT,
    PRIMARY KEY (steam_id, app_id)
);
