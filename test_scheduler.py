"""Unit tests for the SM-2 scheduler — the algorithmic core of LinguaLoop."""
from datetime import datetime

import pytest

from app.services.scheduler import (
    InvalidRatingError,
    apply_review,
    sm2_update,
)


def test_first_review_good_sets_interval_to_one_day():
    ef, interval, reps = sm2_update(ease_factor=2.5, interval_days=0, repetition_count=0, rating="good")
    assert interval == 1
    assert reps == 1


def test_second_consecutive_good_sets_interval_to_six_days():
    ef, interval, reps = sm2_update(ease_factor=2.5, interval_days=1, repetition_count=1, rating="good")
    assert interval == 6
    assert reps == 2


def test_third_consecutive_good_multiplies_by_ease_factor():
    ef, interval, reps = sm2_update(ease_factor=2.5, interval_days=6, repetition_count=2, rating="good")
    assert interval == round(6 * 2.5)
    assert reps == 3


def test_again_resets_repetition_and_interval():
    # Simulate a card with a long history that then gets forgotten.
    ef, interval, reps = sm2_update(ease_factor=2.3, interval_days=30, repetition_count=5, rating="again")
    assert reps == 0
    assert interval == 1


def test_easy_increases_ease_factor_more_than_good():
    ef_good, _, _ = sm2_update(ease_factor=2.5, interval_days=6, repetition_count=2, rating="good")
    ef_easy, _, _ = sm2_update(ease_factor=2.5, interval_days=6, repetition_count=2, rating="easy")
    assert ef_easy > ef_good


def test_again_lowers_ease_factor_more_than_hard():
    ef_again, _, _ = sm2_update(ease_factor=2.5, interval_days=6, repetition_count=2, rating="again")
    ef_hard, _, _ = sm2_update(ease_factor=2.5, interval_days=6, repetition_count=2, rating="hard")
    assert ef_again < ef_hard


def test_ease_factor_never_drops_below_floor():
    ef = 1.3
    for _ in range(10):
        ef, _, _ = sm2_update(ease_factor=ef, interval_days=1, repetition_count=0, rating="again")
    assert ef >= 1.3


def test_invalid_rating_raises():
    with pytest.raises(InvalidRatingError):
        sm2_update(ease_factor=2.5, interval_days=1, repetition_count=0, rating="terrible")


class _FakeCard:
    """Minimal stand-in for the Card model, so apply_review can be tested
    without needing a database session."""

    def __init__(self):
        self.ease_factor = 2.5
        self.interval_days = 0
        self.repetition_count = 0
        self.next_review_at = None


def test_apply_review_sets_next_review_at_in_the_future():
    card = _FakeCard()
    now = datetime(2026, 1, 1)
    apply_review(card, "good", now=now)
    assert card.next_review_at > now
    assert (card.next_review_at - now).days == 1  # first good review -> 1 day


def test_apply_review_sequence_matches_expected_sm2_curve():
    """A card reviewed 'good' four times in a row should follow the
    classic SM-2 curve: 1 day, 6 days, then interval * ease_factor each time.
    """
    card = _FakeCard()
    now = datetime(2026, 1, 1)

    apply_review(card, "good", now=now)
    assert card.interval_days == 1

    apply_review(card, "good", now=now)
    assert card.interval_days == 6

    interval_before_third = card.interval_days
    ease_factor_before_third = card.ease_factor
    apply_review(card, "good", now=now)
    assert card.interval_days == round(interval_before_third * ease_factor_before_third)
