"""
SchedulerService: SM-2 spaced-repetition logic.

Implemented as a pure function first (easy to unit test in isolation),
with a thin wrapper that applies the result to a Card row. This mirrors
the "pure function of (current card state, rating) -> new card state"
design noted in the Week 1 design dump.

LinguaLoop uses a 4-button UI (Again / Hard / Good / Easy) instead of
SM-2's original 0-5 quality scale. The mapping below is the same
simplification used by Anki-style apps:

    again -> 0   (failed recall; treat as a lapse)
    hard  -> 3   (recalled, but with real difficulty)
    good  -> 4   (recalled correctly with some effort)
    easy  -> 5   (recalled correctly and effortlessly)
"""
from datetime import datetime, timedelta

RATING_TO_QUALITY = {
    "again": 0,
    "hard": 3,
    "good": 4,
    "easy": 5,
}

MIN_EASE_FACTOR = 1.3


class InvalidRatingError(ValueError):
    pass


def sm2_update(ease_factor: float, interval_days: int, repetition_count: int, rating: str):
    """Pure SM-2 step.

    Args:
        ease_factor: current ease factor (starts at 2.5 for a new card).
        interval_days: current interval, in days.
        repetition_count: number of consecutive successful reviews.
        rating: one of 'again' | 'hard' | 'good' | 'easy'.

    Returns:
        (new_ease_factor, new_interval_days, new_repetition_count)
    """
    if rating not in RATING_TO_QUALITY:
        raise InvalidRatingError(
            f"rating must be one of {list(RATING_TO_QUALITY)}, got {rating!r}"
        )

    quality = RATING_TO_QUALITY[rating]

    if quality < 3:
        # Lapse: start the interval over, but don't touch ease_factor here —
        # ease_factor is adjusted below regardless of pass/fail, per SM-2.
        new_repetition_count = 0
        new_interval_days = 1
    else:
        if repetition_count == 0:
            new_interval_days = 1
        elif repetition_count == 1:
            new_interval_days = 6
        else:
            new_interval_days = round(interval_days * ease_factor)
        new_repetition_count = repetition_count + 1

    # Ease factor update (standard SM-2 formula), clamped to a floor of 1.3
    # so a card never gets scheduled so aggressively it becomes unreviewable.
    new_ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease_factor = max(MIN_EASE_FACTOR, new_ease_factor)

    return new_ease_factor, new_interval_days, new_repetition_count


def apply_review(card, rating: str, now: datetime = None):
    """Apply a review rating to a Card model instance in place.

    Does not commit the session — callers control the transaction so this
    can be composed with writing a ReviewHistory row in the same commit.
    """
    now = now or datetime.utcnow()

    new_ef, new_interval, new_reps = sm2_update(
        ease_factor=card.ease_factor,
        interval_days=card.interval_days,
        repetition_count=card.repetition_count,
        rating=rating,
    )

    card.ease_factor = new_ef
    card.interval_days = new_interval
    card.repetition_count = new_reps
    card.next_review_at = now + timedelta(days=new_interval)
    return card
