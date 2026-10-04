# LinguaLoop — Sprint 3

**Status:** week of Oct 4, 2026. Third full development sprint. Target
completion date for the full application: **October 18, 2026**. A written
testing plan is due the week ending Oct 11; the application is finalized
and presented the week ending Oct 18 — see `TESTING_PLAN.md`.

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
- 30 automated tests (`pytest`), covering the SM-2 algorithm, the full
  extract → accept/reject → review pipeline, candidate pagination, the
  streak calculation, provider-selection scaffolding, **and (new this
  sprint) input validation and real-provider failure handling**. Plus 4
  live-API-gated tests (skipped by default — see "Testing" below).
- **New this sprint:** real-provider network failures (timeout, bad
  response, rate limit) are caught and surfaced as a clean `502` instead
  of crashing the app — directly relevant now that the app is meant to
  actually be tested against a live translation API before Oct 18.
- **New this sprint:** basic input validation on the two endpoints a
  learner's own typing reaches most directly — pasted text (`POST
  /api/sources`) and review ratings (`POST /api/reviews/:id`) — so a
  malformed request 400s cleanly instead of failing deep inside spaCy or
  the scheduler.

## Sprint 3 changes at a glance

1. **Error handling for real API providers.** `TranslationServiceError`
   and `DefinitionServiceError` (`app/services/translation.py`,
   `app/services/definition.py`) wrap any network failure, timeout, bad
   HTTP status, or unexpected response shape from a real provider into one
   predictable, catchable exception. `accept_candidate()` in
   `app/routes.py` now catches these specifically and returns a `502`
   with a clear message, rather than letting a flaky API call during the
   live presentation surface as a raw, unhandled `500`. The candidate row
   is left untouched on failure, so the user can just retry.
2. **Input validation.** `POST /api/sources` now rejects non-string
   `text`/`title` and caps passage length at `MAX_SOURCE_TEXT_LENGTH`
   (20,000 characters) — nothing in sprints 1-2 stopped an entire
   article or book chapter from being pasted in and flooding the
   candidates table from one request. `POST /api/reviews/:id` now rejects
   a non-string `rating` before it reaches the scheduler.
3. **Live-API-gated test suite** (`tests/test_live_providers.py`). Real
   network calls against MyMemory and the Free Dictionary API are written
   and `pytest.mark.skipif`-gated behind `RUN_LIVE_API_TESTS=1`, so they
   stay skipped (not silently absent) in this sandbox and are ready to run
   for real on a machine with normal internet access.
4. **Testing plan** (`TESTING_PLAN.md`) covering unit/integration/live
   test levels, a manual test checklist, known limitations, and the
   go/no-go schedule from Oct 11 to Oct 18.
5. **Re-verified the `MIN_SENTENCE_TOKENS` limitation with new test
   sentences** (see "Known limitations" below) rather than just carrying
   the sprint 2 note forward unchanged — the threshold was kept at 4
   because raising it further didn't eliminate the underlying tagging
   error, it only reduced how often it's seen.

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
this dev environment confirmed *again* this sprint that it can't make
outbound calls to arbitrary external APIs (a direct request to a public
translation API was attempted and blocked at the network layer). That
block is a property of this specific development sandbox, not of a normal
computer with internet access — so the fix isn't more code here, it's
testing the existing provider classes from a machine that isn't
network-restricted.

**Recommended next real step:** `translation.py` now includes
`MyMemoryTranslationProvider`, which needs **no API key or signup** —
the lowest-friction option to actually verify against a live API. On a
normal internet connection:
```
LINGUALOOP_TRANSLATION_PROVIDER=mymemory python run.py
```
`GoogleTranslateProvider` (higher quality, needs an API key) and
`FreeDictionaryAPIProvider` (for definitions, also no key needed) are the
other stubs, ready to switch on the same way via environment variable
once tested outside this sandbox.

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

To try the real-provider switches (untestable in this sandbox, but wired up
and ready to test on a machine with normal internet access):
```
# no signup needed — try this one first
LINGUALOOP_TRANSLATION_PROVIDER=mymemory python run.py

# higher quality, needs an API key
LINGUALOOP_TRANSLATION_PROVIDER=google GOOGLE_TRANSLATE_API_KEY=... python run.py

LINGUALOOP_DEFINITION_PROVIDER=free_dictionary python run.py
```

## Running the tests

```
pytest tests/ -v
```
This runs all 30 sandbox-safe tests; the 4 live-API tests in
`tests/test_live_providers.py` report as skipped (expected — see that
file's docstring). To actually run them on a machine with normal internet
access:
```
RUN_LIVE_API_TESTS=1 pytest tests/test_live_providers.py -v
```
See `TESTING_PLAN.md` for the full testing strategy and the manual test
checklist.

## Known limitations

- **Real translation/definition providers are still untested from inside
  this sandbox** — confirmed again this sprint via a direct request
  attempt. The code (`MyMemoryTranslationProvider`,
  `FreeDictionaryAPIProvider`) and the live-gated tests are ready; they
  need to be run once on a machine with normal internet access before
  Oct 18, per `TESTING_PLAN.md`.
- **`MIN_SENTENCE_TOKENS` (currently 4) reduces, but does not eliminate,
  spaCy mistagging short/ambiguous words.** Re-tested this sprint with
  additional sentences at and above the threshold — e.g. "Elle lit un
  livre." (4 tokens, at the threshold) still mistags "lit" (verb "reads")
  as a noun, the same category of error the threshold was added to
  reduce. Raising the threshold further would cut even more legitimate
  short sentences without fully solving the underlying tagging ambiguity,
  so it's left at 4 and documented as a known accuracy trade-off rather
  than tuned further without real passage data to tune against.
- **No authentication.** Every request operates against a single demo
  user, an explicit scope decision given the Oct 18 deadline (see
  `_get_or_create_demo_user()` in `app/routes.py`).

## What's next (targeting Oct 18 completion)

- Actually run the live-API-gated tests and the MyMemory/Free Dictionary
  providers on a machine with normal internet access — the single
  biggest remaining risk to the Oct 18 date, since it can't be verified
  in this sandbox. Tracked in `TESTING_PLAN.md`.
- Basic auth, only if time allows — still lower priority than finishing the
  core feature set.
- Continue the UI pass if time allows (the current styling is functional but
  basic).
- Final presentation materials for the week of Oct 18.
