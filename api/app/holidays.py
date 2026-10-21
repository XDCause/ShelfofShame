"""Queensland's public holidays, worked out from the rules (no outside site to ask): the fixed days with their
weekend substitutes, Easter, Labour Day (1st Monday in May), the King's Birthday (1st Monday in October), and the
Ekka's People's Day (Brisbane only: the Wednesday between 10 and 16 August). The Queensland government's list
(qld.gov.au) is the word on it - a year with a one-off change (a royal funeral, a moved Ekka) won't show here.
"""
from datetime import date, timedelta


def easter(year: int) -> date:
    """Easter Sunday (the Gregorian calendar's rule, Meeus / Jones / Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7          # noqa: E741 (the algorithm's own letters)
    m = (a + 11 * h + 22 * l) // 451
    n = h + l - 7 * m + 114
    return date(year, n // 31, n % 31 + 1)


def _first(year: int, month: int, weekday: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def _next_weekday(d: date) -> date:
    return d + timedelta(days={5: 2, 6: 1}.get(d.weekday(), 0))


def queensland(year: int) -> list[tuple[date, str]]:
    """The year's public holidays in Queensland, in date order: (day, name)."""
    out = []

    def fixed(d: date, name: str):
        out.append((d, name))
        if d.weekday() >= 5:                                   # on a weekend: the Monday is a holiday too
            out.append((_next_weekday(d), f"{name} (holiday)"))

    fixed(date(year, 1, 1), "New Year's Day")
    fixed(date(year, 1, 26), "Australia Day")
    e = easter(year)
    out += [(e - timedelta(days=2), "Good Friday"), (e - timedelta(days=1), "Easter Saturday"),
            (e, "Easter Sunday"), (e + timedelta(days=1), "Easter Monday")]
    out.append((date(year, 4, 25), "Anzac Day"))
    out.append((_first(year, 5, 0), "Labour Day"))
    tenth = date(year, 8, 10)
    out.append((tenth + timedelta(days=(2 - tenth.weekday()) % 7), "Ekka People's Day (Brisbane)"))
    out.append((_first(year, 10, 0), "King's Birthday"))
    out.append((date(year, 12, 24), "Christmas Eve (from 6 pm)"))
    christmas, boxing = date(year, 12, 25), date(year, 12, 26)
    out += [(christmas, "Christmas Day"), (boxing, "Boxing Day")]
    taken = {christmas, boxing}
    for day, name in ((christmas, "Christmas Day"), (boxing, "Boxing Day")):
        if day.weekday() >= 5:                                 # the next weekday not already a holiday
            sub = _next_weekday(day)
            while sub in taken:
                sub += timedelta(days=1)
            taken.add(sub)
            out.append((sub, f"{name} (holiday)"))
    return sorted(out)


def holidays_between(start: date, end: date) -> list[dict]:
    """[{day, name}] between two days (inclusive)."""
    return [{"day": d, "name": n} for y in range(start.year, end.year + 1) for d, n in queensland(y) if start <= d <= end]
