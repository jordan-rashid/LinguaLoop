"""
Flask routes implementing the revised API surface from the Week 1
(Revised) design dump. Candidate accept/reject endpoints were added in
sprint 1; sprint 2 adds pagination to the candidates listing.
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from app.models import Candidate, Card, KnownWord, ReviewHistory, Source, User, db
from app.services.definition import create_definition_service
from app.services.extraction import extract_candidates
from app.services.scheduler import InvalidRatingError, apply_review
from app.services.translation import create_translation_service

bp = Blueprint("api", __name__, url_prefix="/api")

translation_service = create_translation_service()
definition_service = create_definition_service()

# Sprint 2: default page size for candidate review, addressing the peer
# feedback that a long passage could dump dozens of words onto one screen.
CANDIDATE_PAGE_SIZE = 10


def _get_or_create_demo_user():
    """Sprint 1 has no auth yet (AuthService is still an open item), so
    every request operates against a single demo user. Good enough to
    exercise the full pipeline; real auth is future work.
    """
    user = User.query.first()
    if not user:
        user = User(email="demo@lingualoop.local", display_name="Demo User", target_language="fr")
        db.session.add(user)
        db.session.commit()
    return user


# ---------------------------------------------------------------- sources --

@bp.route("/sources", methods=["POST"])
def submit_source():
    """POST /api/sources — submit a pasted passage; triggers extraction."""
    payload = request.get_json(force=True) or {}
    text = (payload.get("text") or "").strip()
    title = payload.get("title")

    if not text:
        return jsonify({"error": "text is required"}), 400

    user = _get_or_create_demo_user()
    source = Source(user_id=user.id, raw_text=text, title=title)
    db.session.add(source)
    db.session.flush()  # get source.id before extraction uses it

    candidates = extract_candidates(user.id, source.id, text, language=user.target_language)
    db.session.commit()

    return jsonify({
        "source_id": source.id,
        "candidates_created": len(candidates),
    }), 201


@bp.route("/sources/<int:source_id>/candidates", methods=["GET"])
def list_candidates_for_source(source_id):
    """GET /api/sources/:id/candidates — candidates awaiting accept/reject.

    Sprint 2: paginated via ?limit=&offset=, addressing the review
    feedback that a long passage could surface dozens of candidates onto
    one screen at once. Defaults to CANDIDATE_PAGE_SIZE per page if the
    caller doesn't specify a limit.
    """
    try:
        limit = int(request.args.get("limit", CANDIDATE_PAGE_SIZE))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400

    limit = max(1, min(limit, 100))  # sane bounds regardless of what's requested
    offset = max(0, offset)

    base_query = Candidate.query.filter_by(source_id=source_id)
    total = base_query.count()
    page = base_query.order_by(Candidate.id).offset(offset).limit(limit).all()

    return jsonify({
        "candidates": [_candidate_to_dict(c) for c in page],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page) < total,
    })


# ------------------------------------------------------------- candidates --

@bp.route("/candidates/<int:candidate_id>/accept", methods=["POST"])
def accept_candidate(candidate_id):
    """POST /api/candidates/:id/accept — fetch translation + definition,
    create the card, remove the candidate row.
    """
    candidate = Candidate.query.get_or_404(candidate_id)
    user = User.query.get(candidate.user_id)

    translation = translation_service.translate(candidate.headword, source_lang=user.target_language)
    definition = definition_service.define(candidate.headword, language=user.target_language)

    card = Card(
        user_id=candidate.user_id,
        source_id=candidate.source_id,
        headword=candidate.headword,
        context_sentence=candidate.context_sentence,
        translation=translation,
        definition=definition,
        status="active",
        next_review_at=datetime.utcnow(),
    )
    db.session.add(card)
    db.session.delete(candidate)
    db.session.commit()

    return jsonify(_card_to_dict(card)), 201


@bp.route("/candidates/<int:candidate_id>", methods=["DELETE"])
def reject_candidate(candidate_id):
    """DELETE /api/candidates/:id — reject before any translation is fetched."""
    candidate = Candidate.query.get_or_404(candidate_id)
    db.session.delete(candidate)
    db.session.commit()
    return "", 204


# ------------------------------------------------------------------ cards --

@bp.route("/cards/<int:card_id>", methods=["PATCH"])
def edit_card(card_id):
    """PATCH /api/cards/:id — edit translation/definition/context after creation."""
    card = Card.query.get_or_404(card_id)
    payload = request.get_json(force=True) or {}

    for field in ("translation", "definition", "context_sentence"):
        if field in payload:
            setattr(card, field, payload[field])

    db.session.commit()
    return jsonify(_card_to_dict(card))


@bp.route("/cards/<int:card_id>", methods=["DELETE"])
def archive_card(card_id):
    """DELETE /api/cards/:id — archive an existing active card."""
    card = Card.query.get_or_404(card_id)
    card.status = "archived"
    db.session.commit()
    return "", 204


# --------------------------------------------------------------- reviews --

@bp.route("/reviews/due", methods=["GET"])
def reviews_due():
    """GET /api/reviews/due — today's due cards."""
    user = _get_or_create_demo_user()
    now = datetime.utcnow()
    due_cards = (
        Card.query.filter(Card.user_id == user.id)
        .filter(Card.status == "active")
        .filter(Card.next_review_at <= now)
        .all()
    )
    return jsonify([_card_to_dict(c) for c in due_cards])


@bp.route("/reviews/<int:card_id>", methods=["POST"])
def submit_review(card_id):
    """POST /api/reviews/:card_id — submit a rating; runs SM-2 update."""
    card = Card.query.get_or_404(card_id)
    payload = request.get_json(force=True) or {}
    rating = payload.get("rating")

    try:
        apply_review(card, rating)
    except InvalidRatingError as exc:
        return jsonify({"error": str(exc)}), 400

    db.session.add(ReviewHistory(card_id=card.id, rating=rating))
    db.session.commit()

    return jsonify(_card_to_dict(card))


# -------------------------------------------------------------- dashboard --

def _consecutive_day_streak(review_days: set, today) -> int:
    """True consecutive-day streak ending today or yesterday.

    Sprint 1 shipped a placeholder ("days_with_a_review_logged" — just a
    count of distinct days, not necessarily consecutive). This sprint
    replaces it with an actual streak: count backward from today, and
    stop at the first gap. If today has no review yet, the streak still
    counts as "alive" as long as yesterday had one — a learner shouldn't
    see their streak reset to 0 just because they haven't reviewed *yet
    today*.
    """
    if not review_days:
        return 0

    if today not in review_days:
        # Streak isn't broken unless yesterday is also missing.
        if (today - timedelta(days=1)) not in review_days:
            return 0
        cursor = today - timedelta(days=1)
    else:
        cursor = today

    streak = 0
    while cursor in review_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    """GET /api/dashboard — streak, cards-due count, mastery stats."""
    user = _get_or_create_demo_user()
    now = datetime.utcnow()
    today = now.date()

    total_active_cards = Card.query.filter_by(user_id=user.id, status="active").count()
    due_now = (
        Card.query.filter_by(user_id=user.id, status="active")
        .filter(Card.next_review_at <= now)
        .count()
    )
    known_word_count = KnownWord.query.filter_by(user_id=user.id).count()

    review_days = {
        r.reviewed_at.date()
        for r in ReviewHistory.query.join(Card).filter(Card.user_id == user.id).all()
    }
    streak = _consecutive_day_streak(review_days, today)

    return jsonify({
        "cards_due_today": due_now,
        "total_active_cards": total_active_cards,
        "known_words": known_word_count,
        "current_streak_days": streak,
        "days_with_a_review_logged": len(review_days),
    })


@bp.route("/known-words", methods=["POST"])
def mark_known_word():
    """POST /api/known-words — manually mark a word as known."""
    payload = request.get_json(force=True) or {}
    headword = (payload.get("headword") or "").strip().lower()
    if not headword:
        return jsonify({"error": "headword is required"}), 400

    user = _get_or_create_demo_user()
    existing = KnownWord.query.filter_by(user_id=user.id, headword=headword).first()
    if not existing:
        db.session.add(KnownWord(user_id=user.id, headword=headword))
        db.session.commit()

    return jsonify({"headword": headword, "known": True}), 201


# ------------------------------------------------------------- serializers --

def _candidate_to_dict(c: Candidate) -> dict:
    return {
        "id": c.id,
        "headword": c.headword,
        "context_sentence": c.context_sentence,
        "source_id": c.source_id,
    }


def _card_to_dict(c: Card) -> dict:
    return {
        "id": c.id,
        "headword": c.headword,
        "context_sentence": c.context_sentence,
        "translation": c.translation,
        "definition": c.definition,
        "status": c.status,
        "ease_factor": round(c.ease_factor, 3),
        "interval_days": c.interval_days,
        "repetition_count": c.repetition_count,
        "next_review_at": c.next_review_at.isoformat() if c.next_review_at else None,
    }
