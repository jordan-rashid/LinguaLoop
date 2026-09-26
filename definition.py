"""
DefinitionService: fetches a dictionary-style definition for an accepted
candidate word. New in this sprint per peer feedback — translation and
definition are handled by separate providers, since a translation API
alone doesn't reliably return definitions.

Same provider-swap pattern as TranslationService: a working mock for
demoing the pipeline now, and a stub for a real dictionary API once one
is chosen (open item in the Week 1 design dump). Sprint 2 addition:
create_definition_service() reads LINGUALOOP_DEFINITION_PROVIDER so a
real provider can be switched on via environment variable, once chosen
and tested outside this network-restricted sandbox.
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
        # expanded in sprint 2 to cover more realistic full-sentence demo text
        "professeur": "A teacher, especially at a university or secondary level.",
        "leçon": "A period of learning or instruction on a particular subject.",
        "étudiant": "A person studying at a university or college.",
        "explication": "A statement or account that makes something clear.",
        "directeur": "A person who manages or oversees an organization or department.",
        "salle": "A room, especially one for a specific purpose.",
        "classe": "A group of students taught together; also the room they meet in.",
        "employé": "A person employed to work for another, typically for wages.",
        "fenêtre": "An opening in a wall or roof fitted with glass to admit light or air.",
        "bureau": "A desk or office used for work, especially administrative work.",
        "bibliothécaire": "A person who works professionally in a library.",
        "patience": "The capacity to accept delay or difficulty without becoming annoyed.",
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
    """Factory. Reads LINGUALOOP_DEFINITION_PROVIDER ("mock" | "free_dictionary")
    so a real provider can be switched on via environment variable once
    it's chosen and verified outside this sandbox. Defaults to the mock.
    """
    provider_name = os.environ.get("LINGUALOOP_DEFINITION_PROVIDER", "mock").lower()
    if provider_name == "free_dictionary":
        return FreeDictionaryAPIProvider()
    return MockDefinitionProvider()
