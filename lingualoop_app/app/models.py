"""
SQLAlchemy models for LinguaLoop.

Schema matches the revised Week 1 design dump:
- candidates is a separate staging table from cards (fixes the
  accept-before-translate contradiction flagged in peer review).
- cards only ever holds fully-formed rows (translation + definition
  already fetched); there is no 'pending' status.
- SM-2 scheduling fields live directly on Card.
"""
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    display_name = db.Column(db.String(120))
    target_language = db.Column(db.String(8), nullable=False, default="fr")
    proficiency = db.Column(db.String(4), default="A2")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sources = db.relationship("Source", backref="user", lazy=True)
    candidates = db.relationship("Candidate", backref="user", lazy=True)
    cards = db.relationship("Card", backref="user", lazy=True)
    known_words = db.relationship("KnownWord", backref="user", lazy=True)


class Source(db.Model):
    __tablename__ = "sources"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    raw_text = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(200))
    imported_at = db.Column(db.DateTime, default=datetime.utcnow)


class Candidate(db.Model):
    """A word extracted from a passage, awaiting the learner's accept/reject.

    No translation or definition field exists here on purpose: those are
    only fetched once the learner accepts, per the revised workflow.
    """

    __tablename__ = "candidates"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey("sources.id"))
    headword = db.Column(db.String(120), nullable=False)
    context_sentence = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey("sources.id"))
    headword = db.Column(db.String(120), nullable=False)
    context_sentence = db.Column(db.Text, nullable=False)
    translation = db.Column(db.String(255), nullable=False)
    definition = db.Column(db.Text)
    status = db.Column(db.String(12), default="active")  # active | archived

    # SM-2 scheduling fields
    ease_factor = db.Column(db.Float, default=2.5)
    interval_days = db.Column(db.Integer, default=0)
    repetition_count = db.Column(db.Integer, default=0)
    next_review_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviews = db.relationship("ReviewHistory", backref="card", lazy=True)


class ReviewHistory(db.Model):
    __tablename__ = "review_history"

    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    rating = db.Column(db.String(8), nullable=False)  # again | hard | good | easy
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)


class KnownWord(db.Model):
    __tablename__ = "known_words"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    headword = db.Column(db.String(120), primary_key=True)
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
