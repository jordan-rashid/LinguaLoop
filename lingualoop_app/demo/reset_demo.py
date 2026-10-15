"""
Put the app into a clean, repeatable state before a demonstration.

    python demo/reset_demo.py                 # empty database
    python demo/reset_demo.py --seed-history  # empty, plus 3 days of past reviews

The Windows launchers start_demo.bat and start_demo_live.bat call this
for you. Safe to run while the server is up: it empties and recreates the tables
rather than deleting the database file.

--seed-history inserts ONE sample card ("maison") with review records for
the previous three days, so the dashboard can show a multi-day streak
without waiting days. It is demo data, not real usage. The card is
scheduled for tomorrow, so it does not appear in
the daily review queue.
"""
import os
import sys
from datetime import datetime, timedelta

# Allow `python demo/reset_demo.py` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Card, ReviewHistory, Source, User, db


def reset(seed_history: bool) -> None:
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        if seed_history:
            user = User(email="demo@lingualoop.local", display_name="Demo User", target_language="fr")
            db.session.add(user)
            db.session.flush()

            source = Source(user_id=user.id, raw_text="(seeded demo passage)", title="Seeded demo")
            db.session.add(source)
            db.session.flush()

            now = datetime.utcnow()
            card = Card(
                user_id=user.id, source_id=source.id, headword="maison",
                context_sentence="Le chat dort dans la maison.",
                translation="house", definition="A building for human habitation.",
                status="active", ease_factor=2.6, interval_days=6, repetition_count=2,
                next_review_at=now + timedelta(days=1),
            )
            db.session.add(card)
            db.session.flush()

            for days_ago in (3, 2, 1):
                db.session.add(ReviewHistory(
                    card_id=card.id, rating="good", reviewed_at=now - timedelta(days=days_ago)
                ))

        db.session.commit()
    print("Demo database reset" + (" with 3 days of seeded review history." if seed_history else "."))


if __name__ == "__main__":
    reset(seed_history="--seed-history" in sys.argv)
