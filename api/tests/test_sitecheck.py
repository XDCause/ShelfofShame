"""The weekly check of the websites the app reads: results saved per site, failing_since kept while it
keeps failing and cleared when it works again. The checks themselves are faked (no real sites)."""
from app import sitecheck


def fake(results):
    """CHECKS whose checks return / raise what `results` says, in order."""
    def check_for(site):
        def check():
            r = results[site]
            if isinstance(r, Exception):
                raise r
            return r
        return check
    return [(site, "for testing", check_for(site)) for site in results]


def test_results_and_failing_since(client, monkeypatch):
    assert client.get("/api/site-checks").json()["sites"][0]["ok"] is None        # never checked yet
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "XF-1 Flat Black, with a photo",
                                                   "Gameology": sitecheck.Unexpected("no player counts")}))
    sitecheck.run_all()
    got = {s["site"]: s for s in client.get("/api/site-checks").json()["sites"]}
    assert (got["Tamiya"]["ok"], got["Tamiya"]["detail"]) == (True, "XF-1 Flat Black, with a photo")
    assert (got["Gameology"]["ok"], got["Gameology"]["detail"]) == (False, "no player counts")
    since = got["Gameology"]["failing_since"]
    assert since and got["Tamiya"]["failing_since"] is None
    assert client.get("/api/site-checks").json()["failing"] == 1
    # Still failing a week later: failing_since stays the first day. A crash counts as a failure too.
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "ok", "Gameology": TimeoutError("timed out")}))
    sitecheck.run_all()
    got = {s["site"]: s for s in client.get("/api/site-checks").json()["sites"]}
    assert got["Gameology"]["failing_since"] == since and got["Gameology"]["detail"] == "TimeoutError: timed out"
    # Working again: cleared.
    monkeypatch.setattr(sitecheck, "CHECKS", fake({"Tamiya": "ok", "Gameology": "Catan: 3-4 players"}))
    sitecheck.run_all()
    got = {s["site"]: s for s in client.get("/api/site-checks").json()["sites"]}
    assert got["Gameology"]["ok"] and got["Gameology"]["failing_since"] is None


def test_run_now_starts_it(client, monkeypatch):
    ran = []
    monkeypatch.setattr(sitecheck, "run_all", lambda: ran.append(1))
    assert client.post("/api/site-checks/run").status_code == 202
    assert ran == [1]


def test_every_real_check_is_listed():
    assert len({site for site, _, _ in sitecheck.CHECKS}) == len(sitecheck.CHECKS) >= 10
