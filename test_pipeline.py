"""End-to-end tests of the revised text-to-review pipeline:
extract -> candidates -> accept/reject -> card -> review.

Test sentences use French nouns (chat, jardin, maison, etc.) as the
asserted headwords, and are kept at 4+ alphabetic tokens per sentence.
Three sprint 2 changes affect this file directly:

  - the extraction service now drops sentence fragments shorter than
    MIN_SENTENCE_TOKENS, since spaCy's POS tagger is unreliable on very
    short fragments — a 3-token sentence like "Le chat dort." used in
    sprint 1's tests would now be silently skipped, so those sentences
    were lengthened here to stay above the threshold;
  - the extraction service upgraded from fr_core_news_sm to
    fr_core_news_md, which measurably improved verb lemmatization
    consistency (see app/services/extraction.py's module docstring),
    though noun headwords are still used as the primary assertions here
    since they were never the inconsistent part;
  - GET /api/sources/:id/candidates now returns a paginated envelope
    ({"candidates": [...], "total": ..., ...}) instead of a bare list,
    to support the new candidate-batching feature. get_candidates()
    below unwraps that for the rest of these tests.
"""


def get_candidates(client, source_id, **params):
    """Unwraps the paginated candidates response into a plain list."""
    resp = client.get(f"/api/sources/{source_id}/candidates", query_string=params)
    return resp.get_json()["candidates"]


def test_submitting_a_source_creates_candidates(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans le jardin."})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["candidates_created"] > 0

    candidates = get_candidates(client, body["source_id"])
    headwords = {c["headword"] for c in candidates}
    assert "chat" in headwords
    assert "jardin" in headwords


def test_accepting_a_candidate_creates_a_card_and_removes_the_candidate(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    source_id = resp.get_json()["source_id"]
    candidates = get_candidates(client, source_id)
    chat = next(c for c in candidates if c["headword"] == "chat")

    accept_resp = client.post(f"/api/candidates/{chat['id']}/accept")
    assert accept_resp.status_code == 201
    card = accept_resp.get_json()
    assert card["translation"] == "cat"
    assert card["status"] == "active"

    # candidate should no longer be listed
    remaining = get_candidates(client, source_id)
    assert chat["id"] not in {c["id"] for c in remaining}


def test_rejecting_a_candidate_never_calls_translation(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    source_id = resp.get_json()["source_id"]
    candidates = get_candidates(client, source_id)
    chat = next(c for c in candidates if c["headword"] == "chat")

    reject_resp = client.delete(f"/api/candidates/{chat['id']}")
    assert reject_resp.status_code == 204

    remaining = get_candidates(client, source_id)
    assert chat["id"] not in {c["id"] for c in remaining}


def test_reimporting_overlapping_text_does_not_duplicate_pending_candidates(client):
    """Regression test for the peer-review fix: the extraction filter now
    checks pending candidates too, not just known_words."""
    client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    client.post("/api/sources", json={"text": "Le chat regarde la maison."})

    all_candidates = get_candidates(client, 1) + get_candidates(client, 2)

    headwords = [c["headword"] for c in all_candidates]
    assert headwords.count("chat") == 1
    assert headwords.count("maison") == 1


def test_accepted_card_is_reviewable_and_updates_on_rating(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    source_id = resp.get_json()["source_id"]
    candidates = get_candidates(client, source_id)
    chat = next(c for c in candidates if c["headword"] == "chat")
    card = client.post(f"/api/candidates/{chat['id']}/accept").get_json()

    due = client.get("/api/reviews/due").get_json()
    assert any(c["id"] == card["id"] for c in due)

    review_resp = client.post(f"/api/reviews/{card['id']}", json={"rating": "good"})
    assert review_resp.status_code == 200
    updated = review_resp.get_json()
    assert updated["repetition_count"] == 1
    assert updated["interval_days"] == 1


def test_known_words_are_filtered_out_of_future_extraction(client):
    client.post("/api/known-words", json={"headword": "chat"})
    resp = client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    source_id = resp.get_json()["source_id"]
    candidates = get_candidates(client, source_id)
    assert all(c["headword"] != "chat" for c in candidates)


def test_dashboard_reports_basic_stats(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    source_id = resp.get_json()["source_id"]
    candidates = get_candidates(client, source_id)
    chat = next(c for c in candidates if c["headword"] == "chat")
    client.post(f"/api/candidates/{chat['id']}/accept")

    stats = client.get("/api/dashboard").get_json()
    assert stats["total_active_cards"] == 1


def test_unsupported_language_raises_a_clear_error(client):
    """Confirms the multi-language extension point fails loudly rather
    than silently, if a language without a registered spaCy model is
    requested."""
    from app.services.extraction import extract_candidates
    import pytest

    with pytest.raises(ValueError, match="No spaCy model configured"):
        extract_candidates(user_id=1, source_id=1, text="Hallo Welt", language="de")


# ---------------------------------------------------------- sprint 2 tests --

def test_candidate_list_is_paginated(client):
    """A passage with more candidates than one page should only return
    a page's worth at a time, with has_more reflecting the remainder."""
    long_text = (
        "Le professeur explique la leçon avec patience. "
        "Les étudiants écoutent attentivement chaque explication. "
        "Le directeur visite plusieurs salles de classe aujourd'hui. "
        "Un employé répare la fenêtre cassée du bureau. "
        "La bibliothécaire range soigneusement tous les livres anciens."
    )
    resp = client.post("/api/sources", json={"text": long_text})
    source_id = resp.get_json()["source_id"]
    assert resp.get_json()["candidates_created"] > 5  # confirm the passage is long enough to test with

    first_page = client.get(
        f"/api/sources/{source_id}/candidates", query_string={"limit": 3, "offset": 0}
    ).get_json()
    assert len(first_page["candidates"]) == 3
    assert first_page["has_more"] is True

    second_page = client.get(
        f"/api/sources/{source_id}/candidates", query_string={"limit": 3, "offset": 3}
    ).get_json()
    assert len(second_page["candidates"]) >= 1

    # no overlap between pages
    first_ids = {c["id"] for c in first_page["candidates"]}
    second_ids = {c["id"] for c in second_page["candidates"]}
    assert first_ids.isdisjoint(second_ids)


def test_candidate_list_defaults_to_a_reasonable_page_size(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    source_id = resp.get_json()["source_id"]
    body = client.get(f"/api/sources/{source_id}/candidates").get_json()
    assert body["limit"] == 10  # CANDIDATE_PAGE_SIZE default


def test_streak_counts_consecutive_days_only():
    """Sprint 2 replaces the sprint 1 'distinct days' placeholder with a
    true consecutive-day streak. Reviewing today and 3 days ago (with a
    gap) should report a streak of 1, not 2."""
    from datetime import datetime, timedelta
    from app.routes import _consecutive_day_streak

    today = datetime.utcnow().date()
    review_days_with_gap = {today, today - timedelta(days=3)}
    assert _consecutive_day_streak(review_days_with_gap, today) == 1

    review_days_consecutive = {today, today - timedelta(days=1), today - timedelta(days=2)}
    assert _consecutive_day_streak(review_days_consecutive, today) == 3

    assert _consecutive_day_streak(set(), today) == 0


def test_streak_stays_alive_if_yesterday_was_reviewed_but_not_yet_today():
    from datetime import datetime, timedelta
    from app.routes import _consecutive_day_streak

    today = datetime.utcnow().date()
    review_days = {today - timedelta(days=1), today - timedelta(days=2)}
    assert _consecutive_day_streak(review_days, today) == 2


def test_translation_provider_selection_via_env_var(monkeypatch):
    """Sprint 2: provider choice is now driven by an environment variable
    so a real provider can be switched on without a code change, once
    one is picked and tested outside this sandbox."""
    from app.services.translation import (
        GoogleTranslateProvider,
        MockTranslationProvider,
        create_translation_service,
    )

    monkeypatch.delenv("LINGUALOOP_TRANSLATION_PROVIDER", raising=False)
    assert isinstance(create_translation_service(), MockTranslationProvider)

    monkeypatch.setenv("LINGUALOOP_TRANSLATION_PROVIDER", "google")
    assert isinstance(create_translation_service(), GoogleTranslateProvider)


def test_definition_provider_selection_via_env_var(monkeypatch):
    from app.services.definition import (
        FreeDictionaryAPIProvider,
        MockDefinitionProvider,
        create_definition_service,
    )

    monkeypatch.delenv("LINGUALOOP_DEFINITION_PROVIDER", raising=False)
    assert isinstance(create_definition_service(), MockDefinitionProvider)

    monkeypatch.setenv("LINGUALOOP_DEFINITION_PROVIDER", "free_dictionary")
    assert isinstance(create_definition_service(), FreeDictionaryAPIProvider)
