"""Reading dive files (diveimport.py): UDDF and Subsurface XML, the made-up samples in tests/fixtures, and a file that
tries to be nasty."""
from pathlib import Path

import pytest

from app import diveimport as di

FIX = Path(__file__).parent / "fixtures"


def test_uddf():
    got = di.parse((FIX / "sample.uddf").read_bytes())
    assert got["format"] == "uddf" and len(got["dives"]) == 1
    d = got["dives"][0]
    assert (d["dived_on"], d["time_in"]) == ("2026-03-14", "08:45")
    assert d["max_depth"] == 21.4 and d["avg_depth"] == 14.9 and d["minutes"] == 30
    assert d["gas_o2"] == 32 and d["tank_l"] == 12.0 and (d["start_bar"], d["end_bar"]) == (200, 65)
    assert d["water_temp"] == 23.8                                       # Kelvin in the file
    assert d["site"] == {"name": "Test Reef", "lat": -27.3, "lon": 153.45}
    assert d["computer"] == "Test Computer" and d["import_key"] == "Test Computer|2026-03-14T08:45:00"
    assert d["samples"][0] == [0, 0.0, 24.0] and len(d["samples"]) == 91
    assert d["samples"][-1][1] == 0.0 and max(s[1] for s in d["samples"]) <= 22


def test_subsurface():
    got = di.parse((FIX / "sample.ssrf").read_bytes())
    assert got["format"] == "subsurface" and len(got["dives"]) == 2
    first, second = got["dives"]
    assert (first["dived_on"], first["time_in"], first["minutes"]) == ("2026-04-02", "09:30", 26)
    assert first["max_depth"] == 20.8 and first["avg_depth"] == 18.1 and first["water_temp"] == 23.5
    assert first["gas_o2"] == 32 and first["tank_l"] == 11.0 and (first["start_bar"], first["end_bar"]) == (200, 70)
    assert first["site"] == {"name": "Made-up Wreck", "lat": -27.36, "lon": 153.48}
    assert (first["buddy"], first["guide"], first["suit"], first["rating"]) == ("Sam", "Alex", "5 mm wetsuit", 4)
    assert first["tags"] == ["wreck", "boat"] and "Fast ascent" in first["notes"]
    assert first["samples"][0] == [0, 0.0, 24.0] and first["samples"][1][2] == 24.0     # a temperature carries forward
    assert second["samples"] == [] and second["gas_o2"] == 21 and second["site"] is None and second["minutes"] == 38


def test_missing_numbers_are_worked_out_or_left_out():
    xml = (b"<divelog><dives><dive date='2026-05-01' time='10:00:00' duration='bogus'>"
           b"<cylinder size='99 l' start='100 bar' end='150 bar' o2='10%'/>"
           b"<divecomputer model='X'><sample time='0:00 min' depth='0 m'/><sample time='1:00 min' depth='10 m'/>"
           b"<sample time='2:00 min' depth='10 m'/><sample time='3:00 min' depth='0 m'/></divecomputer>"
           b"</dive><dive date='nonsense'/></dives></divelog>")
    got = di.parse(xml)["dives"]
    d = got[0]
    assert d["max_depth"] == 10.0 and d["avg_depth"] == pytest.approx(6.7, abs=0.1) and d["minutes"] == 3
    assert d["tank_l"] is None and d["end_bar"] is None and d["start_bar"] == 100       # out of range / wrong way round
    assert d["gas_o2"] == 21                                                            # a hypoxic mix isn't believed
    assert len(got) == 1                                                                # the dive with no date is skipped


def test_namespaces_and_midnight():
    xml = (b'<uddf xmlns="http://www.streit.cc/uddf/3.2/"><profiledata><repetitiongroup><dive>'
           b"<informationbeforedive><datetime>2026-06-01T00:00:00</datetime></informationbeforedive>"
           b"<samples><waypoint><divetime>0</divetime><depth>0</depth></waypoint><waypoint><divetime>600</divetime><depth>5</depth></waypoint></samples>"
           b"</dive></repetitiongroup></profiledata></uddf>")
    d = di.parse(xml)["dives"][0]
    assert d["time_in"] is None and d["minutes"] == 10 and d["computer"] is None and d["import_key"] == "import|2026-06-01T00:00:00"


def test_files_that_are_not_dive_logs():
    for raw, word in [(b"", "readable"), (b"just text", "readable"), (b"<html><body/></html>", "neither"),
                      (b"<uddf><oops></uddf>", "readable"), (b"\xff\xfe\x00junk", "readable")]:
        with pytest.raises(di.DiveFileError, match=word):
            di.parse(raw)


def test_entity_tricks_are_refused():
    bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>'
            b"<divelog><dives>&lol2;</dives></divelog>")
    with pytest.raises(di.DiveFileError, match="DOCTYPE"):
        di.parse(bomb)
    external = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><uddf>&e;</uddf>'
    with pytest.raises(di.DiveFileError, match="DOCTYPE"):
        di.parse(external)


def test_a_huge_file_is_refused():
    with pytest.raises(di.DiveFileError, match="20 MB"):
        di.parse(b" " * (di.MAX_BYTES + 1))


def test_a_very_long_profile_is_thinned():
    rows = "".join(f"<sample time='{s}:00 min' depth='{10 if s != 3 else 25} m'/>" for s in range(0, di.MAX_SAMPLES + 500))
    d = di.parse(f"<divelog><dives><dive date='2026-05-01' time='10:00:00'><divecomputer model='X'>{rows}</divecomputer></dive></dives></divelog>".encode())["dives"][0]
    assert len(d["samples"]) <= di.MAX_SAMPLES + 2 and d["max_depth"] == 25.0
    assert any(s[1] == 25.0 for s in d["samples"])
