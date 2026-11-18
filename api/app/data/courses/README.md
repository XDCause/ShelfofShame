# Built-in language courses

A course teaches a language from nothing, unit by unit (Language learning > Learn). Its content is plain JSON here,
one file per unit: `courses/<code>/uNN.json` (`es` = Spanish). The app reads them at start-up
(api/app/language_course.py), checks them (api/tests/test_language_course.py), and builds each lesson's exercises
from the content - so writing a course is writing words, sentences and short notes, not exercises.

All content is written for this app (no copying from textbooks, Duolingo or other courses). Spanish: Latin American
by default ("ustedes", "carro", "computadora", seseo), with Spain's differences noted where they matter (vosotros,
"vale", "coche", "ordenador").

## A unit file

```json
{
  "unit": 1,
  "title": "Hola",
  "cefr": "A1",
  "goal": "Greet people, say your name and where you're from.",
  "lessons": [
    {
      "id": "es-u01-l1",
      "title": "Greetings",
      "notes": "Short teaching text, plain text with **bold** and line breaks (\n). 40-150 words: what's new in this lesson and how it works, with 1-3 examples. Say WHY (patterns), not just lists.",
      "items": [
        {"es": "hola", "en": "hello", "kind": "word"},
        {"es": "buenos días", "en": "good morning", "kind": "phrase", "accept": ["buen día"], "note": "Until about midday."},
        {"es": "el café", "en": "the coffee", "kind": "word", "gender": "m"},
        {"es": "ser", "en": "to be (what something is)", "kind": "verb"}
      ],
      "sentences": [
        {"es": "Hola, me llamo Ana.", "en": "Hello, my name is Ana.", "focus": "llamo"},
        {"es": "¿Cómo estás?", "en": "How are you?", "accept_en": ["How are you doing?"]}
      ]
    }
  ]
}
```

Fields:
- `unit` 1-60, `title`, `cefr` (A1 / A2 / B1), `goal` (one line: what you can do after it), `lessons` (3-5).
- A lesson: `id` = `<code>-uNN-lM` (unique), `title`, `notes` (the teaching text), `items` (6-12), `sentences` (6-12).
- An item: `es` (with its article for nouns: "el libro", "la mesa"), `en`, `kind` (word / phrase / verb), optional
  `accept` (other right Spanish answers), `accept_en` (other right English answers), `note` (a short tip shown when
  it's introduced), `gender` (m / f, nouns).
- A sentence: `es`, `en`, optional `focus` (one word of the sentence, exactly as written there: the gap in its cloze
  exercise; leave it out and the engine picks a word that's one of the lesson's items), `accept` / `accept_en`.
- Sentences use only words taught so far (this lesson and earlier ones), plus names (Ana, Carlos, México...) and
  obvious cognates. Each item appears in at least one sentence of its lesson or the next. Keep sentences short
  (3-10 words) at A1, up to ~14 at A2. Natural, everyday, varied - no "the pen of my aunt".
- Punctuation as Spanish writes it (¿...? ¡...!); accents always right.

## Exercises the engine makes from it

Introduce (each item: Spanish, meaning, spoken, its note) -> match pairs -> pick the meaning (multiple choice from the
lesson's and earlier items) -> type the Spanish -> listen and type -> put the words in order (a sentence) -> fill the
gap (a sentence's focus word) -> translate a sentence into English (accepting close answers). Mistakes come back at
the end of the lesson. A finished lesson puts its items (and sentences as cloze cards) into the language's flashcard
deck, so the spaced reviews keep them.

## Spanish: the outline (es)

A1 - units 1-15 (writer 1)
1. Hola - greetings, goodbyes, me llamo / ¿cómo te llamas?, soy de..., gracias / por favor / de nada
2. Tú y yo - subject pronouns, ser (soy, eres, es, somos, son), nationalities (gender: mexicano / mexicana), tú vs usted
3. Los números - 0-20, ¿cuántos años tienes?, tengo... años, phone numbers, hay
4. Las cosas - el / la / los / las, un / una, plural -s / -es, everyday objects, gender patterns (-o / -a and exceptions)
5. ¿Cómo es? - adjectives (agreement, after the noun), colours, muy, ser for description
6. ¿Dónde está? - estar for place and feelings, ser vs estar (first look), en / con / de, the house and rooms
7. La familia - mi / tu / su, family words, tener, plural possessives
8. El café - ordering food and drink, quiero / quisiera, la cuenta, numbers 20-100, prices
9. Mi día - regular -ar verbs in the present (hablar, trabajar, estudiar), days of the week, a qué hora
10. Comer y vivir - regular -er / -ir verbs (comer, beber, vivir, escribir), questions and no
11. La hora - telling the time, por la mañana / tarde / noche, routine words
12. Me gusta - gustar (me gusta / me gustan), hobbies, también / tampoco
13. La ciudad - places in town, ir + a, a + el = al, directions (a la derecha, todo recto)
14. Ir a... - ir a + infinitive (the near future), weekend plans, months, seasons
15. El tiempo - weather (hace calor, llueve), querer / poder (stem changes e->ie, o->ue), invitations

A2 - units 16-30 (writer 2)
16. Me levanto - reflexive verbs (levantarse, ducharse), the daily routine in full
17. De compras - clothes, sizes, este / ese / aquel, ¿cuánto cuesta?, colours again
18. Ayer - the preterite of regular verbs (-ar, -er / -ir), ayer / la semana pasada
19. ¿Qué hiciste? - irregular preterites (ser / ir, hacer, tener, estar), telling what happened
20. Antes - the imperfect (era, había, -aba / -ía), childhood, used to
21. Contar una historia - preterite vs imperfect together
22. El cuerpo y la salud - the body, me duele, at the doctor, tener que
23. Viajar - travel words, at the airport / hotel, por vs para (first look)
24. La comida - food in more detail, cooking verbs, recipes, the impersonal se
25. Lo, la, le - direct and indirect object pronouns
26. He viajado - the present perfect (haber + participle), ya / todavía no, experiences
27. Comparar - más / menos que, tan... como, the best / worst, mejor / peor
28. Mañana - the future tense (hablaré), plans and predictions, si + present
29. Por favor, ayúdame - commands (tú, usted), giving instructions, at a recipe / directions
30. Mi vida - review: talking about yourself across tenses, opinions (creo que, pienso que), linking words
