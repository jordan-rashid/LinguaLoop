# LinguaLoop — Sprint 1

**Status:** end of week 4 of 8. First full development sprint.

## What works end-to-end

- Paste a French passage (web form at `/`, or `POST /api/sources`).
- Real spaCy tokenization/lemmatization (`fr_core_news_sm`) extracts candidate
  vocabulary, filtered against known words, existing active cards, **and**
  pending candidates (the cross-import dedup fix from peer review).
- Candidate review screen (`/candidates/<source_id>`) — accept or reject each
  word before any translation is fetched, per the revised workflow.
- Accepting a candidate calls `TranslationService` + `DefinitionService`
  (currently mocked — see "What's mocked" below) and creates a `Card` row
  directly in `active` status. Rejecting deletes the candidate; nothing is
  ever half-created.
- SM-2 spaced-repetition scheduler (`app/services/scheduler.py`), fully unit
  tested — 4-button rating (Again/Hard/Good/Easy), ease factor, interval, and
  next-review-date all update correctly.
- Daily review screen (`/review`) shows only cards actually due, and
  submitting a rating reschedules the card.
- Dashboard (`/dashboard`) reports cards due, total active cards, known
  words, and days with a review logged.
- Full REST API matching the endpoint table in the revised design dump
  (`app/routes.py`), plus the server-rendered pages on top of it.
- 18 automated tests (`pytest`), covering the SM-2 algorithm in isolation and
  the full extract → accept/reject → review pipeline through the API.

## Language: French for now, designed to add more later

The project is built around French (`fr_core_news_sm`) for this sprint, not
because the architecture is French-specific, but because the design was
scoped to one language at a time (see the Week 1 design dump). Everything
outside the extraction/translation layer is already language-agnostic —
`User.target_language` exists precisely so a second language doesn't require
a schema change.

**Adding a language later means:**
1. `python -m spacy download <model_name>` for the new language (e.g.
   `es_core_news_sm` for Spanish, which was actually used and verified
   earlier in this project's design phase before the switch to French).
2. Add an entry to `SUPPORTED_MODELS` in `app/services/extraction.py`
   mapping the language code to that model name.
3. Add matching vocabulary entries (or a real API integration) to
   `TranslationService` and `DefinitionService` for that language code —
   these are already split by provider, so a language-specific dictionary
   API can be swapped in independently of the translation provider.
4. Let a `User` row's `target_language` field pick which model/provider is
   used — the extraction call already accepts `language` as a parameter,
   it currently just defaults to `"fr"`.

Nothing about the `candidates`/`cards` schema, the SM-2 scheduler, or the
API routes changes to support this — multi-language support was flagged as
explicitly out of scope for the 8-week MVP, but the code doesn't box it out
for later.

**One real limitation found while testing this switch:** `fr_core_news_sm`'s
lemmatizer is a rule-based system, and it's noticeably less consistent on
conjugated verbs than on nouns — the same verb form can lemmatize
differently depending on surrounding context (e.g., "mange" → "mange" in
one sentence, "manger" in another), while nouns like "chat" or "maison"
lemmatize the same way every time. The mock dictionaries and tests were
built around nouns for this reason. This is worth revisiting with a larger
spaCy model (`fr_core_news_md`/`lg`) or additional verb-normalization logic
in a later sprint if flashcards for verbs turn out to need it.

## What's mocked (and why)

`TranslationService` and `DefinitionService` currently use small curated
dictionaries (`app/services/translation.py`, `app/services/definition.py`)
instead of a live API. This isn't a shortcut around real work — it's because
the provider decision itself is still an open item from the design phase
(comparing DeepL vs. Google Translate, and picking a dictionary API), and
this dev sandbox can't make outbound calls to arbitrary external APIs. Both
files include a real-provider stub (`GoogleTranslateProvider`,
`FreeDictionaryAPIProvider`) showing the intended integration, ready to
swap in via `create_translation_service()` / `create_definition_service()`
once a provider is chosen and tested with a real API key outside this
environment.

Auth is also stubbed — every request currently operates against a single
demo user (`_get_or_create_demo_user()` in `app/routes.py`). This was an
explicit scope decision: `AuthService` was already flagged as possibly
unnecessary for a single-user MVP demo, so sprint 1 time went to the
extraction/translation/scheduling pipeline instead.

## Running it

```
pip install -r requirements.txt
python -m spacy download fr_core_news_sm
python run.py
```
Then visit `http://localhost:5000`.

## Running the tests

```
pytest tests/ -v
```

## What's next (sprint 2)

- Lock in real translation and definition API providers; swap the mocks.
- Basic auth (even single-form login) if multi-user demo becomes necessary.
- UI pass: the current pages are intentionally unstyled — the core loop was
  the priority this sprint, per the original plan to defer appearance work.
- Candidate batching/pagination for passages that surface a large number of
  new words (flagged in design review, not yet built).
- More accurate consecutive-day streak calculation on the dashboard (current
  version counts distinct days with any review, not true streak length).
