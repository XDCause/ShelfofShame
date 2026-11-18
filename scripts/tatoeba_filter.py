"""Tatoeba's exports -> the rows load-tatoeba.ps1 loads into lang_sentences (A11). Run by load-tatoeba.ps1 in a throwaway
container (python -I, no network); the words are cut and folded by the API's own api/app/langwords.py, so the sentences'
words and the words of your deck are compared the same way.

    python -I tatoeba_filter.py <data dir> <api app dir> <tatoeba lang, e.g. spa> <course, e.g. es> [min words] [max words] [cap]

Reads (all three from https://downloads.tatoeba.org/exports/per_language/, bz2-compressed tsv):
    <lang>_sentences.tsv.bz2      id, lang, text            (the language's sentences - no usernames in this file)
    eng_sentences.tsv.bz2         id, lang, text            (English, for the translations)
    <lang>-eng_links.tsv.bz2      id, english id            (which English sentence translates which)
Writes <data dir>/<course>-en.tsv: PostgreSQL COPY text format, one sentence a line:
    sentence_id, course, text, english (array), words (array), word_count, rarity

Kept: sentences with at least one direct English translation (up to 3 kept) and min-max words (names and numbers
count toward that length but aren't words to know). Names: a word seen capitalised in the middle of sentences and
(almost) never in lower case - Tatoeba is full of Tom and Mary. Rarity: the frequency rank of a sentence's rarest word
across the kept sentences (1 = the most common word). Over the cap, the ones with the commonest words are kept.
"""
import bz2
import collections
import sys
from pathlib import Path


def read_tsv(path: Path):
    with bz2.open(path, "rt", encoding="utf-8", newline="\n") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                yield parts


def copy_field(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def pg_array(items) -> str:
    return "{" + ",".join('"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"' for s in items) + "}"


def main():
    data, code, lang, course = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    lo = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    hi = int(sys.argv[6]) if len(sys.argv) > 6 else 20
    cap = int(sys.argv[7]) if len(sys.argv) > 7 else 200000
    sys.path.insert(0, code)
    import langwords  # noqa: E402 - the API's own (api/app/langwords.py, mounted read-only)

    links = collections.defaultdict(list)
    for parts in read_tsv(data / f"{lang}-eng_links.tsv.bz2"):
        if parts[0].isdigit() and parts[1].isdigit():
            links[int(parts[0])].append(int(parts[1]))

    lower, capital_mid = collections.Counter(), collections.Counter()
    kept = {}
    for parts in read_tsv(data / f"{lang}_sentences.tsv.bz2"):
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        sid, text = int(parts[0]), parts[2].strip()
        words = [piece for piece, is_word in langwords.tokens(text) if is_word]
        for i, w in enumerate(words):                   # (every sentence, for telling names apart)
            if w[:1].islower():
                lower[langwords.fold(w)] += 1
            elif i > 0 and w[:1].isupper():
                capital_mid[langwords.fold(w)] += 1
        if sid in links and lo <= len(words) <= hi and len(text) <= 300:
            kept[sid] = text
    names = {f for f, n in capital_mid.items() if n >= 2 and lower[f] * 20 <= n}

    rows, freq = {}, collections.Counter()
    for sid, text in kept.items():
        forms = [f for f in langwords.forms(text) if f not in names]
        if len(forms) >= 2:
            rows[sid] = forms
            freq.update(forms)
    rank = {f: i + 1 for i, (f, _) in enumerate(freq.most_common())}

    wanted = {e for sid in rows for e in links[sid]}
    english = {}
    for parts in read_tsv(data / "eng_sentences.tsv.bz2"):
        if len(parts) >= 3 and parts[0].isdigit() and int(parts[0]) in wanted:
            english[int(parts[0])] = parts[2].strip()

    out = []
    for sid, forms in rows.items():
        texts = []
        for e in links[sid]:
            t = english.get(e)
            if t and t not in texts:
                texts.append(t)
        if texts:
            out.append((max(rank[f] for f in forms), sid, forms, texts[:3]))
    out.sort()
    out = out[:cap]
    target = data / f"{course}-en.tsv"
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        for rarity, sid, forms, texts in sorted(out, key=lambda r: r[1]):
            f.write("\t".join([str(sid), course, copy_field(kept[sid]), copy_field(pg_array(texts)),
                               copy_field(pg_array(forms)), str(len(forms)), str(rarity)]) + "\n")
    print(f"{len(out)} sentences ({len(kept)} of the right length with an English translation; {len(names)} names "
          f"left out of the words; {len(rank)} different words)")


if __name__ == "__main__":
    main()
