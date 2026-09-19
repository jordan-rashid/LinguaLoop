"""
ExtractionService: turns a pasted passage into Candidate rows.

Per the revised design, a word is filtered out if it already appears in
ANY of:
  - known_words (learner marked it mastered)
  - an active card (already being studied)
  - an existing pending candidate for this user (avoids duplicate
    candidates when two imports overlap in vocabulary)

Only the first review flagged this gap: the original design filtered
known_words alone, which allowed the same word to surface twice if it
showed up in two different imports before either was reviewed.

Target language for this sprint is French (fr_core_news_sm). See the
SUPPORTED_MODELS note below for how another language gets added later.
"""
import re

import spacy

from app.models import Candidate, Card, KnownWord, db

_NLP_CACHE = {}

# Words this short are almost always function words spaCy's stopword list
# misses for some inflections; skip them regardless of POS tag.
MIN_HEADWORD_LENGTH = 3

SUPPORTED_MODELS = {
    "fr": "fr_core_news_sm",
}
# To add another language: 1) `python -m spacy download <model_name>`,
# 2) add its code and model name here, 3) add matching entries to the
# TranslationService/DefinitionService providers for that language code.
# The rest of the pipeline (Candidate/Card schema, SM-2 scheduler, API
# routes) is already language-agnostic — target_language just needs to
# flow through from the User row, which it already does.


def _get_nlp(language: str):
    if language not in _NLP_CACHE:
        model_name = SUPPORTED_MODELS.get(language)
        if not model_name:
            supported = ", ".join(SUPPORTED_MODELS) or "(none configured)"
            raise ValueError(
                f"No spaCy model configured for language {language!r}. "
                f"Supported languages: {supported}."
            )
        _NLP_CACHE[language] = spacy.load(model_name)
    return _NLP_CACHE[language]


def _existing_headwords(user_id: int) -> set:
    """Union of known_words + active cards + pending candidates for a user."""
    known = {kw.headword for kw in KnownWord.query.filter_by(user_id=user_id).all()}
    active_cards = {
        c.headword
        for c in Card.query.filter_by(user_id=user_id, status="active").all()
    }
    pending = {
        c.headword for c in Candidate.query.filter_by(user_id=user_id).all()
    }
    return known | active_cards | pending


def extract_candidates(user_id: int, source_id: int, text: str, language: str = "fr"):
    """Tokenize `text`, filter against existing vocabulary, and persist
    new Candidate rows. Returns the list of newly created Candidate objects.

    Does not commit — caller controls the transaction.
    """
    nlp = _get_nlp(language)
    doc = nlp(text)

    seen_headwords = _existing_headwords(user_id)
    seen_this_pass = set()  # avoid duplicate candidates within one passage
    created = []

    for sent in doc.sents:
        sentence_text = sent.text.strip()
        for token in sent:
            if not token.is_alpha or token.is_stop:
                continue
            if len(token.text) < MIN_HEADWORD_LENGTH:
                continue

            headword = token.lemma_.lower()
            if headword in seen_headwords or headword in seen_this_pass:
                continue

            seen_this_pass.add(headword)
            candidate = Candidate(
                user_id=user_id,
                source_id=source_id,
                headword=headword,
                context_sentence=sentence_text,
            )
            db.session.add(candidate)
            created.append(candidate)

    return created
