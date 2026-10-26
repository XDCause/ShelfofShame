"""Has Google Drive finished uploading the backup? (health check, 2026-10-22)

Google Drive for desktop keeps what it knows in a local SQLite database (metadata_sqlite_db): every item with its Google
file id, name and size, and a queue of changes still to send (the operations table). An item counts as uploaded when
it's there with a Google id (not a local placeholder), the same size, not in the trash (the queue is only reported). This is
how Drive for desktop works today, not a published interface, so anything unexpected answers "can't tell", never a
failure of the backup itself.

backup.ps1 copies the database (with its -wal / -shm) into backups\\.drivefs and runs, in the api container:
    python -m app.drivecheck /backups/.drivefs/metadata_sqlite_db /backups/.drivefs/expected.json
expected.json: [{"name": "hobby_inventory_...dump.gpg", "size": 11864682}, ...] - the files old enough to be up.
It prints {"ok": true|false|null, "checked": n, "pending": [names], "queued": n, "message": "..."}.
"""
import json
import sqlite3
import sys


def check(db_path: str, expected: list[dict]) -> dict:
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.text_factory = bytes
        tables = {r[0].decode() for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"items", "operations"} <= tables:
            return {"ok": None, "checked": 0, "pending": [], "queued": 0,
                    "message": "Google Drive's database isn't laid out as expected (an update?) - can't tell"}
        queued = con.execute("SELECT count(*) FROM operations").fetchone()[0]
        rows = {}
        for item_id, title, size, trashed in con.execute(
                "SELECT id, local_title, file_size, trashed FROM items WHERE is_folder = 0"):
            name = title.decode("utf-8", "replace") if isinstance(title, bytes) else str(title)
            rows.setdefault(name, []).append((item_id.decode() if isinstance(item_id, bytes) else str(item_id), size, trashed))
        con.close()
    except sqlite3.Error as e:
        return {"ok": None, "checked": 0, "pending": [], "queued": 0, "message": f"can't read Google Drive's database ({e})"}
    pending = []
    for f in expected:
        up = any(not str(i).startswith("local") and size == f["size"] and not trashed for i, size, trashed in rows.get(f["name"], []))
        if not up:
            pending.append(f["name"])
    # The queue doesn't decide it (2026-10-26): the check runs seconds after the backup writes tonight's file and removes
    # an old one, so those two changes are always still queued - it was "2 change(s) still queued", red by night two,
    # with every file it checked safely up. Only the files old enough to be up count; the queue is just mentioned.
    ok = not pending
    message = ("all uploaded" if ok else f"{len(pending)} not uploaded yet") + (f" ({queued} newer change(s) queued)" if queued else "")
    return {"ok": ok, "checked": len(expected), "pending": pending[:10], "queued": queued, "message": message}


def main(argv: list[str]) -> int:
    db_path, expected_path = argv
    with open(expected_path, encoding="utf-8-sig") as f:
        expected = json.load(f)
    print(json.dumps(check(db_path, expected)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
