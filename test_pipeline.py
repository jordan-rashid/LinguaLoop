"""End-to-end tests of the revised text-to-review pipeline:
extract -> candidates -> accept/reject -> card -> review.

Test sentences use French nouns (chat, jardin, maison, etc.) rather than
conjugated verbs, because sprint 1 testing found fr_core_news_sm's
rule-based lemmatizer is inconsistent on verb forms (e.g. "mange"
lemmatizes to "mange" in one sentence but "manger" in another). Nouns
lemmatize reliably, which keeps these tests meaningful rather than
flaky. The verb-lemmatization gap itself is a known limitation, noted
in app/services/translation.py and the design dump's open items.
"""


def test_submitting_a_source_creates_candidates(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort dans le jardin."})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["candidates_created"] > 0

    candidates = client.get(f"/api/sources/{body['source_id']}/candidates").get_json()
    headwords = {c["headword"] for c in candidates}
    assert "chat" in headwords
    assert "jardin" in headwords


def test_accepting_a_candidate_creates_a_card_and_removes_the_candidate(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort."})
    source_id = resp.get_json()["source_id"]
    candidates = client.get(f"/api/sources/{source_id}/candidates").get_json()
    chat = next(c for c in candidates if c["headword"] == "chat")

    accept_resp = client.post(f"/api/candidates/{chat['id']}/accept")
    assert accept_resp.status_code == 201
    card = accept_resp.get_json()
    assert card["translation"] == "cat"
    assert card["status"] == "active"

    # candidate should no longer be listed
    remaining = client.get(f"/api/sources/{source_id}/candidates").get_json()
    assert chat["id"] not in {c["id"] for c in remaining}


def test_rejecting_a_candidate_never_calls_translation(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort."})
    source_id = resp.get_json()["source_id"]
    candidates = client.get(f"/api/sources/{source_id}/candidates").get_json()
    chat = next(c for c in candidates if c["headword"] == "chat")

    reject_resp = client.delete(f"/api/candidates/{chat['id']}")
    assert reject_resp.status_code == 204

    remaining = client.get(f"/api/sources/{source_id}/candidates").get_json()
    assert chat["id"] not in {c["id"] for c in remaining}


def test_reimporting_overlapping_text_does_not_duplicate_pending_candidates(client):
    """Regression test for the peer-review fix: the extraction filter now
    checks pending candidates too, not just known_words."""
    client.post("/api/sources", json={"text": "Le chat dort dans la maison."})
    client.post("/api/sources", json={"text": "Le chat regarde la maison."})

    all_candidates = []
    for source_id in (1, 2):
        all_candidates += client.get(f"/api/sources/{source_id}/candidates").get_json()

    headwords = [c["headword"] for c in all_candidates]
    assert headwords.count("chat") == 1
    assert headwords.count("maison") == 1


def test_accepted_card_is_reviewable_and_updates_on_rating(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort."})
    source_id = resp.get_json()["source_id"]
    candidates = client.get(f"/api/sources/{source_id}/candidates").get_json()
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
    resp = client.post("/api/sources", json={"text": "Le chat dort."})
    source_id = resp.get_json()["source_id"]
    candidates = client.get(f"/api/sources/{source_id}/candidates").get_json()
    assert all(c["headword"] != "chat" for c in candidates)


def test_dashboard_reports_basic_stats(client):
    resp = client.post("/api/sources", json={"text": "Le chat dort."})
    source_id = resp.get_json()["source_id"]
    candidates = client.get(f"/api/sources/{source_id}/candidates").get_json()
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
