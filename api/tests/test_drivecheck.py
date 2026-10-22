"""Has Google Drive finished uploading the backup? (app/drivecheck.py) - against a made-up copy of Drive for desktop's
database: uploaded, still uploading, a different size, in the trash, a queue of changes, and a layout it doesn't know."""
import json
import sqlite3

from app import drivecheck


def drive_db(tmp_path, items, queued=0, layout=True):
    path = tmp_path / "metadata_sqlite_db"
    con = sqlite3.connect(path)
    if layout:
        con.execute("CREATE TABLE items (stable_id INTEGER PRIMARY KEY, id TEXT, proto BLOB, trashed INTEGER, is_folder INTEGER, "
                    "file_size INTEGER, local_title TEXT)")
        con.execute("CREATE TABLE operations (id INTEGER PRIMARY KEY, proto BLOB)")
        for name, gid, size, trashed in items:
            con.execute("INSERT INTO items (id, proto, trashed, is_folder, file_size, local_title) VALUES (?, x'00ff', ?, 0, ?, ?)",
                        (gid, trashed, size, name))
        for _ in range(queued):
            con.execute("INSERT INTO operations (proto) VALUES (x'01')")
    else:
        con.execute("CREATE TABLE something_else (x)")
    con.commit()
    con.close()
    return str(path)


DUMP = {"name": "hobby_inventory_20261021_020000.dump.gpg", "size": 11864682}
VIDEO = {"name": "8-5b72aaea3987.mp4.gpg", "size": 4153463277}


def test_everything_uploaded(tmp_path):
    db = drive_db(tmp_path, [(DUMP["name"], "1abcDEF", DUMP["size"], 0), (VIDEO["name"], "1xyz", VIDEO["size"], 0)])
    assert drivecheck.check(db, [DUMP, VIDEO]) == {"ok": True, "checked": 2, "pending": [], "queued": 0, "message": "all uploaded"}


def test_not_there_wrong_size_or_trashed_is_pending(tmp_path):
    db = drive_db(tmp_path, [(DUMP["name"], "1abc", DUMP["size"] - 1, 0), (VIDEO["name"], "1xyz", VIDEO["size"], 1)])
    out = drivecheck.check(db, [DUMP, VIDEO, {"name": "missing.gpg", "size": 5}])
    assert out["ok"] is False and out["pending"] == [DUMP["name"], VIDEO["name"], "missing.gpg"]
    assert out["message"] == "3 not uploaded yet"


def test_a_local_placeholder_or_a_queue_is_not_done(tmp_path):
    db = drive_db(tmp_path, [(DUMP["name"], "local-123", DUMP["size"], 0)], queued=2)
    out = drivecheck.check(db, [DUMP])
    assert out["ok"] is False and out["pending"] == [DUMP["name"]] and "2 change(s) queued" in out["message"]
    db2 = drive_db(tmp_path / "..", [(DUMP["name"], "1abc", DUMP["size"], 0)], queued=1)
    assert drivecheck.check(db2, [DUMP])["message"] == "1 change(s) still queued"


def test_an_unknown_layout_or_no_database_is_cant_tell_not_a_failure(tmp_path):
    assert drivecheck.check(drive_db(tmp_path, [], layout=False), [DUMP])["ok"] is None
    assert drivecheck.check(str(tmp_path / "nope" / "db"), [DUMP])["ok"] is None


def test_the_command_line(tmp_path, capsys):
    db = drive_db(tmp_path, [(DUMP["name"], "1abc", DUMP["size"], 0)])
    (tmp_path / "expected.json").write_text(json.dumps([DUMP]))
    assert drivecheck.main([db, str(tmp_path / "expected.json")]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
