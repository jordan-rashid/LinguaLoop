# LinguaLoop — Sprint 2

**Status:** week of Sep 26, 2026. Second full development sprint. Target
completion date for the full application: **October 18, 2026**.

## What works end-to-end

- Paste a French passage (web form at `/`, or `POST /api/sources`).
- Real spaCy tokenization/lemmatization (`fr_core_news_md`, upgraded this
  sprint) extracts candidate vocabulary, filtered against known words,
  existing active cards, **and** pending candidates (the cross-import dedup
  fix from peer review).
- Candidate review screen (`/candidates/<source_id>`) — accept or reject each
  word before any translation is fetched, per the revised workflow. **New
  this sprint:** paginated 10 at a time, so a long passage no longer dumps
  every extracted word onto one screen.
- Accepting a candidate calls `TranslationService` + `DefinitionService`
  (currently mocked — see "What's mocked" below) and creates a `Card` row
  directly in `active` status. Rejecting deletes the candidate; nothing is
  ever half-created.
- SM-2 spaced-repetition scheduler (`app/services/scheduler.py`), fully unit
  tested — 4-button rating (Again/Hard/Good/Easy), ease factor, interval, and
  next-review-date all update correctly.
- Daily review screen (`/review`) shows only cards actually due, and
  submitting a rating reschedules the card.
- Dashboard (`/dashboard`) reports a **true consecutive-day streak (new this
  sprint)**, cards due, total active cards, and known words.
- A light CSS pass (`app/static/style.css`) — sprint 1 shipped intentionally
  unstyled pages so development time went to the core loop first; this
  sprint added styling now that the loop is proven to work.
- Full REST API matching the endpoint table in the revised design dump
  (`app/routes.py`), plus the server-rendered pages on top of it.
- 24 automated tests (`pytest`), covering the SM-2 algorithm, the full
  extract → accept/reject → review pipeline, candidate pagination, the
  streak calculation, and the new provider-selection scaffolding.

## Sprint 2 changes at a glance

1. **spaCy model upgrade (`fr_core_news_sm` → `fr_core_news_md`).** Sprint 1
   flagged inconsistent verb lemmatization as a known limitation. This
   sprint tested both models side by side on the exact sentence that failed
   before ("Le chien mange du pain dans la maison tous les jours.") — the
   medium model correctly lemmatizes "mange" → "manger" where the small
   model left it as "mange". This is a measurable, verified improvement, not
   a guess. It isn't perfect (genuinely ambiguous words like "court" — which
   can be the adjective "short" or a form of "courir", "to run" — are still
   occasionally mistagged), so a small **minimum-sentence-length filter**
   (`MIN_SENTENCE_TOKENS` in `app/services/extraction.py`) was added
   alongside it: spaCy's tagger turned out to be far less reliable on very
   short fragments than on ordinary full sentences, and a pasted passage is
   mostly full sentences anyway.
2. **Candidate pagination.** `GET /api/sources/:id/candidates` now returns
   `{"candidates": [...], "total", "limit", "offset", "has_more"}` instead of
   a bare list, and the web review screen shows 10 at a time with Previous/
   Next controls. This directly addresses design-review feedback from
   earlier in the project about overcrowding the review screen.
3. **True consecutive-day streak.** Sprint 1's dashboard reported a
   placeholder ("days with a review logged" — a count of distinct days, not
   necessarily consecutive). `_consecutive_day_streak()` in `app/routes.py`
   now counts backward from today (or from yesterday, if today hasn't been
   reviewed yet) and stops at the first gap.
4. **Provider-selection scaffolding.** `create_translation_service()` and
   `create_definition_service()` now read `LINGUALOOP_TRANSLATION_PROVIDER`
   / `LINGUALOOP_DEFINITION_PROVIDER` environment variables, so a real
   provider can be switched on without a code change once one is chosen. The
   mock dictionaries were also expanded to cover more realistic full-sentence
   demo text.
5. **A light UI pass.** Styling, a pagination control, and dashboard stat
   tiles — appearance work deferred from sprint 1 now that the core loop is
   proven correct.

## Language: French for now, designed to add more later

The project is built around French for this sprint, not because the
architecture is French-specific, but because the design was scoped to one
language at a time (see the Week 1 design dump). Everything outside the
extraction/translation layer is already language-agnostic —
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

## What's mocked (and why)

`TranslationService` and `DefinitionService` currently use curated
dictionaries (`app/services/translation.py`, `app/services/definition.py`)
instead of a live API. This isn't a shortcut around real work — the
provider decision itself is still an open item from the design phase
(comparing DeepL vs. Google Translate, and picking a dictionary API), and
this dev sandbox confirmed *again* this sprint that it can't make outbound
calls to arbitrary external APIs (a direct request to a public translation
API was attempted and blocked at the network layer). Both files include a
real-provider stub (`GoogleTranslateProvider`, `FreeDictionaryAPIProvider`)
showing the intended integration, and can now be switched on via an
environment variable (see "Sprint 2 changes" above) once a provider is
chosen and tested with a real API key outside this environment.

Auth is also still stubbed — every request currently operates against a
single demo user (`_get_or_create_demo_user()` in `app/routes.py`). This
remains an explicit scope decision given the Oct 18 deadline: `AuthService`
was already flagged as possibly unnecessary for a single-user MVP demo, so
sprint time continues to go to the core pipeline instead.

## Running it

```
pip install -r requirements.txt
python -m spacy download fr_core_news_md
python run.py
```
Then visit `http://localhost:5000`.

To try the real-provider switches (untestable in this sandbox, but wired up):
```
LINGUALOOP_TRANSLATION_PROVIDER=google GOOGLE_TRANSLATE_API_KEY=... python run.py
```

## Running the tests

```
pytest tests/ -v
```

## What's next (sprint 3, targeting Oct 18 completion)

- Lock in and actually test real translation and definition API providers
  outside this sandbox — this is now the single biggest remaining risk to
  the Oct 18 date, since it's the one piece that can't be verified here.
- Basic auth, only if time allows — still lower priority than finishing the
  core feature set.
- Continue the UI pass if time allows (the current styling is functional but
  basic).
- Revisit the `MIN_SENTENCE_TOKENS` filter's threshold value based on real
  passage testing — 4 was chosen from limited manual testing, not tuned.
