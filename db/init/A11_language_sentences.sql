-- Language learning's reading sentences (2026-11-17): real example sentences from Tatoeba (tatoeba.org, CC BY 2.0 FR),
-- with their English translations, read at your level (Language learning > Read; api/app/language_sentences.py).
-- Loaded by load-tatoeba.ps1 from Tatoeba's exports (kept out of the repo in data\tatoeba); none in a fresh copy.
-- Idempotent.
--   lang_sentences        a sentence in a course's language ('es' = Spanish: lang_languages.course, A10): Tatoeba's own
--                         id (its page: tatoeba.org/en/sentences/show/<id>), the text, its English translation(s), its
--                         words as compared (langwords.fold: lower case, accents off, ñ kept; names and numbers left
--                         out), how many, and how rare its rarest word is (1 = the most common word in the language)
--   lang_sentence_words   the same words, one a row: "which sentences have this word" and the at-your-level counts
--   lang_sentence_seen    the sentences you've read (English shown) in a language, and the card one became. No foreign
--                         key to lang_sentences: reloading the sentences keeps what you've read (Tatoeba's ids stay)
-- No usernames are kept (Tatoeba's "added by"), and no audio (its licences vary; the browser speaks instead).
BEGIN;

CREATE TABLE IF NOT EXISTS lang_sentences (
    sentence_id integer PRIMARY KEY,
    course      text NOT NULL,
    text        text NOT NULL,
    english     text[] NOT NULL,
    words       text[] NOT NULL,
    word_count  smallint NOT NULL,
    rarity      integer NOT NULL DEFAULT 0,
    CONSTRAINT lang_sentences_course_code CHECK (course ~ '^[a-z]{2,3}$'),
    CONSTRAINT lang_sentences_text_filled CHECK (btrim(text) <> ''),
    CONSTRAINT lang_sentences_english_filled CHECK (cardinality(english) >= 1),
    CONSTRAINT lang_sentences_count_fits CHECK (word_count = cardinality(words))
);
CREATE INDEX IF NOT EXISTS lang_sentences_course_idx ON lang_sentences (course);

CREATE TABLE IF NOT EXISTS lang_sentence_words (
    course      text NOT NULL,
    word        text NOT NULL,
    sentence_id integer NOT NULL REFERENCES lang_sentences ON DELETE CASCADE,
    PRIMARY KEY (course, word, sentence_id)
);
CREATE INDEX IF NOT EXISTS lang_sentence_words_sentence_idx ON lang_sentence_words (sentence_id);

CREATE TABLE IF NOT EXISTS lang_sentence_seen (
    language_id integer NOT NULL REFERENCES lang_languages ON DELETE CASCADE,
    sentence_id integer NOT NULL,
    seen_at     timestamptz NOT NULL DEFAULT now(),
    card_id     integer REFERENCES lang_cards ON DELETE SET NULL,
    PRIMARY KEY (language_id, sentence_id)
);
CREATE INDEX IF NOT EXISTS lang_sentence_seen_card_idx ON lang_sentence_seen (card_id);

COMMIT;
