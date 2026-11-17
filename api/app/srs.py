"""Spaced repetition for Language learning's cards: FSRS-5 (the Free Spaced Repetition Scheduler - the open algorithm
Anki has used since 23.10, by Jarrett Ye / open-spaced-repetition), written out here from its published formulas.
Pure sums, no database: language_cards.py stores what this returns. Tested directly (tests/test_language.py).

Why FSRS and not SM-2 (Anki's old one): SM-2 multiplies the interval by an "ease" that only ever drifts down after a
miss ("ease hell"), and doesn't know how overdue a card was. FSRS models each card's memory with two numbers and asks
when you'd have a 90% chance of still remembering it - in benchmarks it needs ~20-30% fewer reviews for the same
retention.

    stability S   days until the chance of recalling the card falls to 90% (it grows with each success)
    difficulty D  1-10: how hard this card is for you (Again / Hard push it up, Easy down; it drifts back to the middle)
    retrievability R(t) = (1 + F * t / S) ^ C    the chance you'd recall it t days after the last review
                                                 (F = 19/81, C = -0.5: a power-law forgetting curve, R(S) = 0.9)

A review with grade G (1 Again, 2 Hard, 3 Good, 4 Easy):
    first review   S = w[G-1], D = w4 - e^(w5 (G-1)) + 1
    remembered     S' = S (e^w8 (11 - D) S^-w9 (e^(w10 (1-R)) - 1) * hard / easy factor + 1)   - a longer gap, an
                   easier card and a lower R (you remembered against the odds) all grow it more
    forgot         S' = min(S, w11 D^-w12 ((S+1)^w13 - 1) e^(w14 (1-R)))                         - smaller, not reset
    same day       S' = S e^(w17 (G - 3 + w18))                                                    (a learning step)
    difficulty     D' = D - w6 (G-3) (10-D)/9, then pulled toward D0(Easy) by w7; kept in 1-10
The next interval is the number of days until R falls to the retention you want (RETENTION, 0.9): with 0.9 it's S.

Learning steps (Anki's, simplified): Again on a new or forgotten card brings it back in 1 minute, Hard in 5,
Good on a new card in 10 - so it's seen again in the same sitting; a card graduates to days once it's Good on a
second look (or Easy at once). Intervals are whole days from 1 up to MAX_DAYS, Hard <= Good <= Easy always.
"""
import math
from datetime import datetime, timedelta

# FSRS-5's default parameters (fitted on ~700 million Anki reviews; py-fsrs / ts-fsrs DEFAULT_PARAMETERS).
W = (0.4072, 1.1829, 3.1262, 15.4722, 7.2102, 0.5316, 1.0651, 0.0234, 1.616, 0.1544, 1.0824, 1.9813, 0.0953,
     0.2975, 2.2042, 0.2407, 2.9466, 0.5034, 0.6567)
F, C = 19 / 81, -0.5
RETENTION = 0.9
MAX_DAYS = 36500
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
STEPS = {AGAIN: 1, HARD: 5, GOOD: 10}       # learning steps, minutes


def _clamp_d(d: float) -> float:
    return min(10.0, max(1.0, d))


def retrievability(elapsed_days: float, stability: float) -> float:
    return (1 + F * max(0.0, elapsed_days) / stability) ** C


def init_stability(grade: int) -> float:
    return max(W[grade - 1], 0.1)


def init_difficulty(grade: int) -> float:
    return W[4] - math.exp(W[5] * (grade - 1)) + 1


def next_difficulty(d: float, grade: int) -> float:
    delta = -W[6] * (grade - 3)
    d2 = d + delta * (10 - d) / 9                                  # (linear damping: harder to move near 10)
    return _clamp_d(W[7] * init_difficulty(EASY) + (1 - W[7]) * d2)   # (mean reversion)


def recall_stability(d: float, s: float, r: float, grade: int) -> float:
    hard = W[15] if grade == HARD else 1
    easy = W[16] if grade == EASY else 1
    return s * (math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1)


def forget_stability(d: float, s: float, r: float) -> float:
    return min(s, W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r)))


def short_term_stability(s: float, grade: int) -> float:
    return s * math.exp(W[17] * (grade - 3 + W[18]))


def interval_days(stability: float, retention: float = RETENTION) -> int:
    days = stability / F * (retention ** (1 / C) - 1)
    return int(min(MAX_DAYS, max(1, round(days))))


def review(card: dict, grade: int, now: datetime) -> dict:
    """The card's memory after answering `grade` now. card: state, stability, difficulty, last_review, reps, lapses.
    Returns state, stability, difficulty, due, interval_days (0 = minutes away), reps, lapses."""
    if grade not in (AGAIN, HARD, GOOD, EASY):
        raise ValueError("grade must be 1-4")
    state = card.get("state") or "new"
    s, d = card.get("stability"), card.get("difficulty")
    reps, lapses = (card.get("reps") or 0) + 1, card.get("lapses") or 0
    last = card.get("last_review")
    elapsed = (now - last).total_seconds() / 86400 if last else 0.0

    if state == "new" or s is None or d is None:
        s, d = init_stability(grade), _clamp_d(init_difficulty(grade))
        r = 1.0
    else:
        r = retrievability(elapsed, s)
        d_next = next_difficulty(d, grade)
        if elapsed < 1:                         # seen again the same day (a learning step, or a second look)
            s = short_term_stability(s, grade)
        elif grade == AGAIN:
            s = forget_stability(d, s, r)
        else:
            s = recall_stability(d, s, r, grade)
        d = d_next
    s = max(0.1, min(float(MAX_DAYS), s))

    learning = state in ("new", "learning", "relearning")
    if grade == AGAIN:
        if state == "review":
            lapses += 1
        nxt = "relearning" if state in ("review", "relearning") else "learning"
        minutes = STEPS[AGAIN]
    elif learning and grade == HARD:
        nxt, minutes = state if state != "new" else "learning", STEPS[HARD]
    elif state == "new" and grade == GOOD:
        nxt, minutes = "learning", STEPS[GOOD]
    else:
        nxt, minutes = "review", None
    if minutes is not None:
        return {"state": nxt, "stability": s, "difficulty": d, "due": now + timedelta(minutes=minutes),
                "interval_days": 0, "reps": reps, "lapses": lapses}

    days = interval_days(s)
    if state == "review":                       # keep Hard <= Good <= Easy for a review card
        good = interval_days(recall_stability(card["difficulty"], card["stability"], r, GOOD)) if elapsed >= 1 else days
        if grade == HARD:
            days = min(days, good)
        elif grade == EASY:
            days = max(days, good + 1)
    return {"state": "review", "stability": s, "difficulty": d, "due": now + timedelta(days=days),
            "interval_days": days, "reps": reps, "lapses": lapses}


def preview(card: dict, now: datetime) -> dict:
    """What each grade would do: {1: '1m', 2: '5m', 3: '3d', 4: '8d'} - shown on the grade buttons."""
    return {g: label(review(card, g, now), now) for g in (AGAIN, HARD, GOOD, EASY)}


def label(after: dict, now: datetime) -> str:
    secs = (after["due"] - now).total_seconds()
    if secs < 3600:
        return f"{max(1, round(secs / 60))}m"
    days = after["interval_days"] or round(secs / 86400)
    if days < 31:
        return f"{days}d"
    if days < 365:
        return f"{days / 30.4:.1f}mo".replace(".0mo", "mo")
    return f"{days / 365:.1f}y".replace(".0y", "y")
