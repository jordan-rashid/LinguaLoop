"""Entry point for running LinguaLoop.

Windows, easiest:    double-click start_lingualoop.bat (sets everything up)
Local development:   python run.py
Deployed / hosted:   gunicorn "run:app"      (see README, "Deployment")

Settings come from environment variables so the same code runs unchanged
on a laptop and on a host:
    PORT              port to listen on (default 5000)
    LINGUALOOP_DEBUG  "1" enables Flask's debug mode (default "1" locally;
                      set to "0" in any deployed environment)
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0" if os.environ.get("PORT") else "127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("LINGUALOOP_DEBUG", "1") == "1",
    )
