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

Target language for this sprint is French (fr_core_news_md). See the
SUPPORTED_MODELS note below for how another language gets added later.

Sprint 2 update: upgraded from fr_core_news_sm to fr_core_news_md after
sprint 1 flagged inconsistent verb lemmatization as a known limitation.
Side-by-side testing on the exact sentence that failed in sprint 1
("Le chien mange du pain dans la maison tous les jours.") confirmed the
medium model correctly lemmatizes "mange" -> "manger" where the small
model returned "mange" (i.e., left it unlemmatized). The medium model
still isn't perfect — genuinely ambiguous words like "court" (can be the
adjective "short" or a form of the verb "courir", "to run") are still
occasionally mistagged — but this is a real, measurable improvement on
ordinary, full-length sentences, which is what a pasted passage will
mostly consist of.
"""
import re

import spacy

from app.models import Candidate, Card, KnownWord, db

_NLP_CACHE = {}

# Words this short are almost always function words spaCy's stopword list
# misses for some inflections; skip them regardless of POS tag.
MIN_HEADWORD_LENGTH = 3

# Sentences shorter than this (in alphabetic tokens) are dropped from
# extraction entirely. Sprint 2 finding: spaCy's POS tagger is far less
# reliable on very short fragments ("Le chat mange." mistags "mange" as
# a noun) than on ordinary full sentences, because there isn't enough
# surrounding context to disambiguate. Since a real passage is made of
# full sentences, this trades a small amount of recall on fragments for
# a meaningful accuracy gain on the vocabulary that actually gets shown
# to the learner.
MIN_SENTENCE_TOKENS = 4

SUPPORTED_MODELS = {
    "fr": "fr_core_news_md",
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
        alpha_token_count = sum(1 for t in sent if t.is_alpha)
        if alpha_token_count < MIN_SENTENCE_TOKENS:
            continue

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
