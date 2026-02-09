"""Web layer (Flask blueprints)."""

from __future__ import annotations

from flask import Flask

from .api_exo import bp as exo_bp
from .main import bp as main_bp


def register_blueprints(app: Flask) -> None:
	app.register_blueprint(main_bp)
	app.register_blueprint(exo_bp)

