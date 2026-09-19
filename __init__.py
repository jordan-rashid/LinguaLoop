import os

from flask import Flask, redirect, render_template, request, url_for

from app.models import Candidate, Card, db


def create_app(test_config: dict = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    db_path = os.path.join(app.instance_path, "lingualoop.db")
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
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


def _register_web_views(app: Flask):
    """Minimal server-rendered pages so sprint 1 can be demoed by hand,
    without needing a separate frontend build. This is intentionally
    plain (no styling) — per the plan, appearance work comes after the
    core loop works, and low-fidelity wireframes are the design-time
    stand-in for this until the real UI is built.
    """

    @app.route("/")
    def import_page():
        return render_template("import.html")

    @app.route("/import", methods=["POST"])
    def do_import():
        import requests

        text = request.form.get("text", "")
        with app.test_client() as client:
            resp = client.post("/api/sources", json={"text": text})
        data = resp.get_json()
        return redirect(url_for("candidates_page", source_id=data["source_id"]))

    @app.route("/candidates/<int:source_id>")
    def candidates_page(source_id):
        candidates = Candidate.query.filter_by(source_id=source_id).all()
        return render_template("candidates.html", candidates=candidates, source_id=source_id)

    @app.route("/candidates/<int:candidate_id>/accept", methods=["POST"])
    def accept_candidate_web(candidate_id):
        source_id = request.form.get("source_id")
        with app.test_client() as client:
            client.post(f"/api/candidates/{candidate_id}/accept")
        return redirect(url_for("candidates_page", source_id=source_id))

    @app.route("/candidates/<int:candidate_id>/reject", methods=["POST"])
    def reject_candidate_web(candidate_id):
        source_id = request.form.get("source_id")
        with app.test_client() as client:
            client.delete(f"/api/candidates/{candidate_id}")
        return redirect(url_for("candidates_page", source_id=source_id))

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
            client.post(f"/api/reviews/{card_id}", json={"rating": rating})
        return redirect(url_for("review_page"))

    @app.route("/dashboard")
    def dashboard_page():
        with app.test_client() as client:
            resp = client.get("/api/dashboard")
        return render_template("dashboard.html", stats=resp.get_json())
