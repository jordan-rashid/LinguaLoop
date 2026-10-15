"""
LinguaLoop application package.

Layout (the layers a request passes through):

    templates/ + static/   -> presentation: server-rendered pages
    app/__init__.py        -> web views: thin form handlers that call the API
    app/routes.py          -> API layer: validation, HTTP status codes, JSON
    app/services/          -> business logic: extraction, translation,
                              definition, SM-2 scheduling (no Flask imports)
    app/models.py          -> data layer: SQLAlchemy models over SQLite

The web views deliberately call the JSON API (through Flask's test client)
instead of touching the database themselves, so the browser pages and the
REST API can never drift apart in behavior.
"""
import os

from flask import Flask, flash, redirect, render_template, request, url_for

from app.models import Candidate, Card, db


def create_app(test_config: dict = None) -> Flask:
    """Application factory: builds and configures a Flask app.

    Using a factory (instead of a module-level app) lets the tests create a
    fresh app with a throwaway in-memory database for every test.
    """
    app = Flask(__name__, instance_relative_config=True)

    db_path = os.path.join(app.instance_path, "lingualoop.db")
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Needed only so flash() messages can be stored in the session.
        # Override with LINGUALOOP_SECRET_KEY for any real deployment.
        SECRET_KEY=os.environ.get("LINGUALOOP_SECRET_KEY", "dev-only-not-a-secret"),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from app.routes import bp as api_bp
    app.register_blueprint(api_bp)

    _register_web_views(app)

    with app.app_context():
        db.create_all()

    return app


# Sprint 2: candidate pages are paginated to match the API's pagination
# (see CANDIDATE_PAGE_SIZE in app/routes.py) — a long passage no longer
# dumps every extracted word onto one screen.
WEB_CANDIDATE_PAGE_SIZE = 10


def _register_web_views(app: Flask):
    """Server-rendered pages so the pipeline can be used by hand without a
    separate frontend build.

    Final sprint: every view now checks the API's response instead of
    assuming success, and reports problems (empty input, a translation
    service outage) or results (what was added, when a card returns) to the
    user with a flash message rather than crashing or failing silently.
    """

    @app.route("/")
    def import_page():
        return render_template("import.html")

    @app.route("/import", methods=["POST"])
    def do_import():
        text = request.form.get("text", "")
        with app.test_client() as client:
            resp = client.post("/api/sources", json={"text": text})
        data = resp.get_json()

        if resp.status_code != 201:
            flash(data.get("error", "Could not import that passage."), "error")
            return redirect(url_for("import_page"))

        if data["candidates_created"] == 0:
            flash("No new vocabulary found — every word was already known, "
                  "in your deck, or pending review.", "info")
        return redirect(url_for("candidates_page", source_id=data["source_id"]))

    @app.route("/candidates/<int:source_id>")
    def candidates_page(source_id):
        page = max(1, request.args.get("page", 1, type=int))
        offset = (page - 1) * WEB_CANDIDATE_PAGE_SIZE

        base_query = Candidate.query.filter_by(source_id=source_id).order_by(Candidate.id)
        total = base_query.count()
        candidates = base_query.offset(offset).limit(WEB_CANDIDATE_PAGE_SIZE).all()

        total_pages = max(1, (total + WEB_CANDIDATE_PAGE_SIZE - 1) // WEB_CANDIDATE_PAGE_SIZE)

        return render_template(
            "candidates.html",
            candidates=candidates,
            source_id=source_id,
            page=page,
            total_pages=total_pages,
            total=total,
        )

    @app.route("/candidates/<int:candidate_id>/accept", methods=["POST"])
    def accept_candidate_web(candidate_id):
        source_id = request.form.get("source_id")
        page = request.form.get("page", 1)
        with app.test_client() as client:
            resp = client.post(f"/api/candidates/{candidate_id}/accept")
        data = resp.get_json()

        if resp.status_code == 201:
            flash(f"Added “{data['headword']}” — {data['translation']}", "success")
        else:
            # e.g. 502 when the live translation API is down. The candidate
            # was left untouched by the API, so the user can simply retry.
            flash(data.get("error", "Could not add that word."), "error")
        return redirect(url_for("candidates_page", source_id=source_id, page=page))

    @app.route("/candidates/<int:candidate_id>/reject", methods=["POST"])
    def reject_candidate_web(candidate_id):
        source_id = request.form.get("source_id")
        page = request.form.get("page", 1)
        with app.test_client() as client:
            client.delete(f"/api/candidates/{candidate_id}")
        return redirect(url_for("candidates_page", source_id=source_id, page=page))

    @app.route("/candidates/<int:candidate_id>/known", methods=["POST"])
    def known_candidate_web(candidate_id):
        """'I already know this word': add it to the known-words list (so
        future imports skip it) and clear it from the pending candidates."""
        source_id = request.form.get("source_id")
        page = request.form.get("page", 1)
        candidate = Candidate.query.get_or_404(candidate_id)
        headword = candidate.headword
        with app.test_client() as client:
            client.post("/api/known-words", json={"headword": headword})
            client.delete(f"/api/candidates/{candidate_id}")
        flash(f"Marked “{headword}” as known — it won't be suggested again.", "info")
        return redirect(url_for("candidates_page", source_id=source_id, page=page))

    @app.route("/review")
    def review_page():
        from datetime import datetime
        now = datetime.utcnow()
        due = (
            Card.query.filter_by(status="active")
            .filter(Card.next_review_at <= now)
            .all()
        )
        return render_template("review.html", cards=due)

    @app.route("/review/<int:card_id>", methods=["POST"])
    def submit_review_web(card_id):
        rating = request.form.get("rating")
        with app.test_client() as client:
            resp = client.post(f"/api/reviews/{card_id}", json={"rating": rating})
        data = resp.get_json()

        if resp.status_code == 200:
            days = data["interval_days"]
            when = "tomorrow" if days == 1 else f"in {days} days"
            flash(f"“{data['headword']}” rated {rating} — you'll see it again {when}.", "success")
        else:
            flash(data.get("error", "Could not save that rating."), "error")
        return redirect(url_for("review_page"))

    @app.route("/dashboard")
    def dashboard_page():
        with app.test_client() as client:
            resp = client.get("/api/dashboard")
        return render_template("dashboard.html", stats=resp.get_json())
