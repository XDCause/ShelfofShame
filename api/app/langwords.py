"""Words in a sentence, the same way everywhere (language_sentences.py and the Tatoeba loader, scripts/tatoeba_filter.py):
pure Python, no imports from the app, so the loader can use it outside the API.

    tokens(text)   the sentence cut into pieces: words and what's between them (spaces, punctuation), in order
    fold(word)     a word as it's compared: lower case, accents off (tú = tu, está = esta) but ñ kept (año is not ano)
    forms(text)    the distinct folded words of a text (numbers and punctuation left out)

A word is a run of letters, with an apostrophe inside it kept ("l'eau"); digits end a word and aren't words.
"""
import re
import unicodedata

WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")


def fold(word: str) -> str:
    s = (word or "").lower().replace("’", "'").replace("ñ", "\0")
    s = "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", s).replace("\0", "ñ")


def tokens(text: str) -> list[tuple[str, bool]]:
    """[(piece, is_word)] - joined back together they're the text exactly."""
    out, at = [], 0
    for m in WORD.finditer(text or ""):
        if m.start() > at:
            out.append((text[at:m.start()], False))
        out.append((m.group(0), True))
        at = m.end()
    if at < len(text or ""):
        out.append((text[at:], False))
    return out


def forms(text: str) -> list[str]:
    seen = []
    for m in WORD.finditer(text or ""):
        f = fold(m.group(0))
        if f not in seen:
            seen.append(f)
    return seen
