"""Language learning's reading (language_sentences.py, langwords.py): words cut and folded, what you know, sentences at
your level (just right = one unknown word, easy = none), looking up a word, marking one read, and a sentence into the
deck as a cloze. Fixture rows only: nothing is ever downloaded here (load-tatoeba.ps1 loads the real ones)."""
from app import langwords
from app.db import db
from app.language_sentences import card_forms, cloze_front, marked

SENTENCES = [  # Tatoeba-like rows (made-up ids and text)
    (101, "Tom está en casa.", ["Tom is at home."]),            # Tom: a name (not a word to know)
    (102, "El perro come en casa.", ["The dog eats at home."]),
    (103, "El gato duerme.", ["The cat sleeps.", "The cat is sleeping."]),
    (104, "Tengo 3 perros y un gato.", ["I have 3 dogs and a cat."]),
    (105, "¿Dónde está el año nuevo?", ["Where is the new year?"]),
]
NAMES = {"tom"}


def load(course="es"):
    with db() as conn:
        for sid, text, english in SENTENCES:
            words = [w for w in langwords.forms(text) if w not in NAMES]
            conn.execute("INSERT INTO lang_sentences (sentence_id, course, text, english, words, word_count, rarity) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s)", (sid, course, text, english, words, len(words), sid))
        conn.execute("INSERT INTO lang_sentence_words (course, word, sentence_id) "
                     "SELECT course, unnest(words), sentence_id FROM lang_sentences")


def spanish(client, course="es", name="Spanish"):
    r = client.post("/api/language/languages", json={"name": name, "voice": "es-ES"})
    assert r.status_code == 201
    with db() as conn:     # (the course: A10's column - set here so this test doesn't depend on how a language gets one)
        conn.execute("UPDATE lang_languages SET course = %s WHERE language_id = %s", (course, r.json()["language_id"]))
    return r.json()["language_id"]


def card(client, lid, front, back="x"):
    assert client.post("/api/language/cards", json={"language_id": lid, "front": front, "back": back}).status_code == 201


# ---------------------------------------------------------------- pure
def test_words_are_cut_and_folded():
    assert langwords.fold("Está") == "esta" and langwords.fold("AÑO") == "año" and langwords.fold("pingüino") == "pinguino"
    text = "¿Dónde está el año 2026, Tom?"
    assert "".join(p for p, _ in langwords.tokens(text)) == text
    assert [p for p, w in langwords.tokens(text) if w] == ["Dónde", "está", "el", "año", "Tom"]
    assert langwords.forms("El perro y EL gato") == ["el", "perro", "y", "gato"]
    assert langwords.forms("l'eau d’été") == ["l'eau", "d'ete"]


def test_what_a_card_teaches():
    assert card_forms("word", "el perro (m.)") == ["el", "perro"]
    assert card_forms("cloze", "Ayer {{fui::ir}} al {{cine}}") == ["fui", "cine"]
    assert card_forms("word", "") == []


def test_a_sentence_marked_for_the_page():
    row = {"sentence_id": 101, "text": "Tom está en casa.", "english": ["Tom is at home."], "words": ["esta", "en", "casa"],
           "word_count": 3, "rarity": 5}
    m = marked(row, {"en", "casa"})
    assert m["unknown"] == ["esta"] and m["url"] == "https://tatoeba.org/en/sentences/show/101"
    assert [(p["text"], p["word"], p["unknown"]) for p in m["pieces"]] == [
        ("Tom", None, False), (" ", None, False), ("está", "esta", True), (" ", None, False), ("en", "en", False),
        (" ", None, False), ("casa", "casa", False), (".", None, False)]


def test_cloze_front():
    assert cloze_front("¿Dónde está el año nuevo?", "ano") is None
    assert cloze_front("¿Dónde está el año nuevo?", "año") == "¿Dónde está el {{año}} nuevo?"
    assert cloze_front("Está bien, está.", "esta") == "{{Está}} bien, está."


# ---------------------------------------------------------------- the routes
def test_nothing_loaded_or_no_course(client):
    lid = spanish(client)
    r = client.get(f"/api/language/sentences?language_id={lid}").json()
    assert r["total"] == 0 and r["sentences"] == [] and "Tatoeba" in r["credit"]
    load()
    fr = spanish(client, course=None, name="French")
    r = client.get(f"/api/language/sentences?language_id={fr}&level=any").json()
    assert r["course"] is None and r["total"] == 0 and r["sentences"] == []
    assert client.get("/api/language/sentences?language_id=999999").status_code == 404
    assert client.get(f"/api/language/sentences?language_id={lid}&level=hard").status_code == 422


def test_sentences_at_your_level(client):
    load()
    lid = spanish(client)
    base = f"/api/language/sentences?language_id={lid}"
    r = client.get(base).json()
    assert r["total"] == 5 and r["known_words"] == 0 and r["sentences"] == [] and r["counts"] == {"right": 0, "easy": 0}
    assert len(client.get(base + "&level=any").json()["sentences"]) == 5
    # the deck: "en casa" (a word card's every word), "está" (accents don't matter), a cloze's answer
    card(client, lid, "en casa", "at home")
    card(client, lid, "esta")
    card(client, lid, "El {{perro}} come.", "The dog eats.")
    r = client.get(base + "&level=easy").json()
    assert [s["sentence_id"] for s in r["sentences"]] == [101]                 # Tom's a name: not a word to know
    assert r["known_words"] == 4 and r["counts"] == {"right": 0, "easy": 1}
    assert client.get(base + "&level=right").json()["sentences"] == []        # "El perro come en casa": el, come unknown
    # one more known word: "El perro come en casa" is just right (come: no stemming, comer doesn't make it known)
    card(client, lid, "el")
    card(client, lid, "comer")
    r = client.get(base + "&level=right").json()
    assert [s["sentence_id"] for s in r["sentences"]] == [102] and r["sentences"][0]["unknown"] == ["come"]
    assert r["counts"] == {"right": 1, "easy": 1}
    unknown = [p["text"] for p in r["sentences"][0]["pieces"] if p["unknown"]]
    assert unknown == ["come"]


def test_look_up_a_word(client):
    load()
    lid = spanish(client)
    card(client, lid, "el gato")
    r = client.get(f"/api/language/sentences?language_id={lid}&word=GATO").json()
    assert r["word"] == "gato" and [s["sentence_id"] for s in r["sentences"]] == [103, 104]   # fewest unknown first
    assert client.get(f"/api/language/sentences?language_id={lid}&word=two words").status_code == 422
    assert client.get(f"/api/language/sentences?language_id={lid}&word=zzz").json()["sentences"] == []


def test_seen_and_into_the_deck(client):
    load()
    lid = spanish(client)
    for w in ("el", "dónde", "nuevo"):
        card(client, lid, w)
    assert client.post("/api/language/sentences/105/seen", json={"language_id": lid}).json() == {"seen": True}
    assert client.post("/api/language/sentences/105/seen", json={"language_id": lid}).status_code == 200     # (again: fine)
    assert client.post("/api/language/sentences/999/seen", json={"language_id": lid}).status_code == 404
    assert client.post("/api/language/sentences/105/seen", json={"language_id": 999999}).status_code == 404
    any_ = client.get(f"/api/language/sentences?language_id={lid}&level=any").json()["sentences"]
    assert any_[-1]["sentence_id"] == 105 and any_[-1]["seen"]                 # read ones come last
    # into the deck: the unknown word of a sentence (está, año: the first), or the one tapped
    r = client.post("/api/language/sentences/105/card", json={"language_id": lid})
    assert r.status_code == 201 and r.json()["word"] == "esta"
    c = r.json()["card"]
    assert c["kind"] == "cloze" and c["front"] == "¿Dónde {{está}} el año nuevo?" and c["back"] == "Where is the new year?"
    assert "tatoeba.org/en/sentences/show/105" in c["notes"] and c["tags"] == ["tatoeba"]
    assert client.post("/api/language/sentences/105/card", json={"language_id": lid}).json()["word"] == "año"
    assert client.post("/api/language/sentences/105/card", json={"language_id": lid, "word": "año"}).status_code == 409
    assert client.post("/api/language/sentences/105/card", json={"language_id": lid, "word": "gato"}).status_code == 422
    assert client.post("/api/language/sentences/105/card", json={"language_id": lid}).status_code == 422     # all known now
    r = client.get(f"/api/language/sentences?language_id={lid}&level=easy").json()
    assert 105 in [s["sentence_id"] for s in r["sentences"]]                   # its words count as known at once
    with db() as conn:
        assert conn.execute("SELECT card_id FROM lang_sentence_seen WHERE sentence_id = 105").fetchone()["card_id"]
    # a sentence of another course isn't this language's
    fr = spanish(client, course="fr", name="French")
    assert client.post("/api/language/sentences/105/card", json={"language_id": fr}).status_code == 404
