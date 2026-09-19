"""
DefinitionService: fetches a dictionary-style definition for an accepted
candidate word. New in this sprint per peer feedback — translation and
definition are handled by separate providers, since a translation API
alone doesn't reliably return definitions.

Same provider-swap pattern as TranslationService: a working mock for
demoing the pipeline now, and a stub for a real dictionary API once one
is chosen (open item in the Week 1 design dump).
"""
import os


class DefinitionProvider:
    def define(self, word: str, language: str) -> str:
        raise NotImplementedError


class MockDefinitionProvider(DefinitionProvider):
    _SAMPLE_DEFINITIONS = {
        "chat": "A small domesticated carnivorous mammal (feline).",
        "chien": "A domesticated carnivorous mammal, typically kept as a pet.",
        "jardin": "A piece of ground used for growing plants, flowers, or vegetables.",
        "jour": "A period of 24 hours; the time between sunrise and sunset.",
        "maison": "A building for human habitation.",
        "livre": "A written or printed work consisting of pages bound together.",
        "eau": "A colorless, transparent, odorless liquid essential for life.",
        "ami": "A person with whom one has a bond of mutual affection.",
        "école": "An institution for educating children or adults.",
        "ville": "A large town; a center of population, commerce, and culture.",
        "nuit": "The period from sunset to sunrise.",
        "temps": "A continuous, measurable quantity of duration; also 'weather'.",
        "pain": "A staple food made from flour, water, and yeast, then baked.",
        "voiture": "A road vehicle with an engine, used for transporting people.",
        "table": "A piece of furniture with a flat top and one or more legs.",
    }

    def define(self, word: str, language: str) -> str:
        return self._SAMPLE_DEFINITIONS.get(
            word.lower(), f"[definition for '{word}' not found in mock dictionary]"
        )


class FreeDictionaryAPIProvider(DefinitionProvider):
    """Stub for a real dictionary API integration (e.g. a language-specific
    equivalent of the Free Dictionary API). Untested in this sandbox for
    the same outbound-network reason noted in TranslationService.
    """

    BASE_URL = "https://api.dictionaryapi.dev/api/v2/entries"

    def define(self, word: str, language: str) -> str:
        import requests

        resp = requests.get(f"{self.BASE_URL}/{language}/{word}", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data[0]["meanings"][0]["definitions"][0]["definition"]
        except (KeyError, IndexError):
            return "[no definition returned]"


def create_definition_service() -> DefinitionProvider:
    """Factory — swap this once a real dictionary API is chosen."""
    return MockDefinitionProvider()
