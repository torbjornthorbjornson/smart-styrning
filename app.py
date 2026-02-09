from __future__ import annotations

from flask import Flask

from smartweb_backend.web import register_blueprints


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    register_blueprints(app)
    return app


# gunicorn/systemd entrypoint expects: app:app
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
