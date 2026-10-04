"""
TranslationService: fetches a translation for an accepted candidate word.

Split out from DefinitionService per peer feedback — a translation API
(Google Translate, DeepL) is not a reliable source of dictionary-style
definitions, so the two are separate providers behind the same interface.

The concrete provider is still an open item in the Week 1 design dump
(comparing DeepL vs. Google Translate on cost/rate limits). Sprint 2
re-checked outbound network access from this dev environment specifically
to see if that decision could finally be tested — it's still blocked
(confirmed by a direct request attempt during this sprint), so this
remains:
  - a working MockTranslationProvider (curated FR->EN dictionary,
    expanded this sprint) so the rest of the pipeline can be built and
    demoed end-to-end now,
  - a MyMemoryTranslationProvider, added specifically because it needs no
    API key or signup — the lowest-friction real option to actually test
    from a machine with normal internet access,
  - a GoogleTranslateProvider stub showing a higher-quality real
    integration, which needs an API key and outbound network access this
    sandboxed dev environment doesn't have.

Both real providers are untested from inside this sandbox, not because
the code is wrong, but because this environment cannot reach either API.
That testing has to happen on a machine with normal internet access.

Sprint 2 addition: create_translation_service() now reads
LINGUALOOP_TRANSLATION_PROVIDER so a real provider can be switched on
with an environment variable once one is chosen and tested outside this
sandbox, instead of needing a code change.

Sprint 3 addition: a TranslationServiceError wraps any network failure,
timeout, or bad response from a real provider into one predictable
exception type. Before this, a flaky API call during the live
presentation would have surfaced as a raw 500 with a stack trace; now
routes.py can catch TranslationServiceError specifically and return a
clear "translation service unavailable, try again" response instead.
"""
import os


class TranslationServiceError(Exception):
    """Raised when a real translation provider fails — network error,
    timeout, bad HTTP status, or an unexpected response shape. The mock
    provider never raises this, since it never leaves the process."""


class TranslationProvider:
    def translate(self, word: str, source_lang: str, target_lang: str = "en") -> str:
        raise NotImplementedError


class MockTranslationProvider(TranslationProvider):
    """Small curated dictionary so sprint 1 can be demoed without a live
    API key. NOT meant to cover arbitrary vocabulary — just enough common
    French words to exercise the full accept -> translate -> card pipeline.

    Nouns were chosen deliberately: sprint 1 testing found that
    fr_core_news_sm's rule-based lemmatizer is inconsistent on conjugated
    verbs (e.g. "mange" lemmatizes to "mange" in one sentence but
    "manger" in another), while nouns lemmatize reliably. That's a real
    limitation to revisit — see the extraction service validation note
    in the design dump's open items — not something papered over here.
    """

    _SAMPLE_DICT = {
        "chat": "cat",
        "chien": "dog",
        "jardin": "garden",
        "jour": "day",
        "maison": "house",
        "livre": "book",
        "eau": "water",
        "ami": "friend",
        "école": "school",
        "ville": "city",
        "nuit": "night",
        "temps": "time / weather",
        "pain": "bread",
        "voiture": "car",
        "table": "table",
        # expanded in sprint 2 to cover more realistic full-sentence demo text
        "professeur": "teacher / professor",
        "leçon": "lesson",
        "étudiant": "student",
        "explication": "explanation",
        "directeur": "director / principal",
        "salle": "room",
        "classe": "class / classroom",
        "employé": "employee",
        "fenêtre": "window",
        "bureau": "office / desk",
        "bibliothécaire": "librarian",
        "patience": "patience",
    }

    def translate(self, word: str, source_lang: str, target_lang: str = "en") -> str:
        return self._SAMPLE_DICT.get(word.lower(), f"[translation for '{word}' not found in mock dictionary]")


class MyMemoryTranslationProvider(TranslationProvider):
    """Real, no-signup translation provider — added specifically to give
    a zero-friction path to finally testing a live API outside this
    sandbox. MyMemory (mymemory.translated.net) requires no API key and
    has a usable free tier for a class project's demo traffic.

    Untested in THIS environment for the same network-block reason as
    GoogleTranslateProvider (confirmed again this sprint), but the request
    is a plain unauthenticated GET, so testing it from a normal internet
    connection should be as simple as:

        LINGUALOOP_TRANSLATION_PROVIDER=mymemory python run.py

    A quick standalone sanity check (run this on your own machine, not in
    this sandbox) before wiring it into the app:

        import requests
        r = requests.get("https://api.mymemory.translated.net/get",
                          params={"q": "chat", "langpair": "fr|en"})
        print(r.json()["responseData"]["translatedText"])
    """

    BASE_URL = "https://api.mymemory.translated.net/get"

    def __init__(self, contact_email: str = None):
        # MyMemory raises the free daily word limit substantially if a
        # contact email is included — optional, but worth setting via
        # MYMEMORY_CONTACT_EMAIL if translation volume becomes an issue.
        self.contact_email = contact_email or os.environ.get("MYMEMORY_CONTACT_EMAIL")

    def translate(self, word: str, source_lang: str, target_lang: str = "en") -> str:
        import requests

        params = {"q": word, "langpair": f"{source_lang}|{target_lang}"}
        if self.contact_email:
            params["de"] = self.contact_email

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise TranslationServiceError(
                f"MyMemory request failed for word {word!r}: {exc}"
            ) from exc
        except ValueError as exc:  # resp.json() on a non-JSON body
            raise TranslationServiceError(
                f"MyMemory returned a non-JSON response for word {word!r}: {exc}"
            ) from exc

        status = data.get("responseStatus")
        if status not in (200, "200"):
            raise TranslationServiceError(f"MyMemory returned status {status!r} for word {word!r}")

        try:
            return data["responseData"]["translatedText"]
        except (KeyError, TypeError) as exc:
            raise TranslationServiceError(
                f"MyMemory response for {word!r} was missing the expected fields: {exc}"
            ) from exc


class GoogleTranslateProvider(TranslationProvider):
    """Stub for the real integration. Requires GOOGLE_TRANSLATE_API_KEY.

    Left unimplemented beyond the request shape because this sandbox has
    no outbound network access to translation.googleapis.com — this is
    the piece to finish once a provider is locked in and tested outside
    this environment.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")

    def translate(self, word: str, source_lang: str, target_lang: str = "en") -> str:
        if not self.api_key:
            raise RuntimeError(
                "GoogleTranslateProvider requires GOOGLE_TRANSLATE_API_KEY; "
                "falling back to MockTranslationProvider is recommended in dev."
            )
        import requests  # local import: only needed if this path is actually used

        try:
            resp = requests.post(
                "https://translation.googleapis.com/language/translate/v2",
                params={"key": self.api_key},
                json={"q": word, "source": source_lang, "target": target_lang, "format": "text"},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise TranslationServiceError(
                f"Google Translate request failed for word {word!r}: {exc}"
            ) from exc
        except ValueError as exc:
            raise TranslationServiceError(
                f"Google Translate returned a non-JSON response for word {word!r}: {exc}"
            ) from exc

        try:
            return data["data"]["translations"][0]["translatedText"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationServiceError(
                f"Google Translate response for {word!r} was missing the expected fields: {exc}"
            ) from exc


def create_translation_service() -> TranslationProvider:
    """Factory. Reads LINGUALOOP_TRANSLATION_PROVIDER ("mock" | "mymemory" |
    "google") so a real provider can be switched on via environment
    variable once it's chosen and verified outside this sandbox, without
    a code change. Defaults to the mock provider.

    "mymemory" is the recommended first thing to actually test on a real
    machine — it needs no API key, unlike "google".
    """
    provider_name = os.environ.get("LINGUALOOP_TRANSLATION_PROVIDER", "mock").lower()
    if provider_name == "mymemory":
        return MyMemoryTranslationProvider()
    if provider_name == "google":
        return GoogleTranslateProvider()
    return MockTranslationProvider()
