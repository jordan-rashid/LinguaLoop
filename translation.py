"""
TranslationService: fetches a translation for an accepted candidate word.

Split out from DefinitionService per peer feedback — a translation API
(Google Translate, DeepL) is not a reliable source of dictionary-style
definitions, so the two are separate providers behind the same interface.

The concrete provider is still an open item in the Week 1 design dump
(comparing DeepL vs. Google Translate on cost/rate limits). This sprint
ships:
  - a working MockTranslationProvider (small curated ES->EN dictionary)
    so the rest of the pipeline can be built and demoed end-to-end now,
  - a GoogleTranslateProvider stub showing the intended real integration,
    which needs an API key and outbound network access this sandboxed
    dev environment doesn't have — it is untested here, not because the
    code is wrong, but because it can't reach the real API from this box.

Swapping providers is a one-line change in create_translation_service().
"""
import os


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
    }

    def translate(self, word: str, source_lang: str, target_lang: str = "en") -> str:
        return self._SAMPLE_DICT.get(word.lower(), f"[translation for '{word}' not found in mock dictionary]")


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

        resp = requests.post(
            "https://translation.googleapis.com/language/translate/v2",
            params={"key": self.api_key},
            json={"q": word, "source": source_lang, "target": target_lang, "format": "text"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["data"]["translations"][0]["translatedText"]


def create_translation_service() -> TranslationProvider:
    """Factory — swap this to GoogleTranslateProvider() once a provider
    and API key are locked in."""
    return MockTranslationProvider()
