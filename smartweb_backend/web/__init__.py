"""Web layer (Flask blueprints)."""

from __future__ import annotations

from flask import Flask

from .main import bp as main_bp


def register_blueprints(app: Flask) -> None:
	app.register_blueprint(main_bp)
