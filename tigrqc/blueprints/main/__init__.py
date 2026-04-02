"""A blueprint that provides the main views of the application.

This includes:
    - A home page with a listing of projects
    - The ability to add new projects
"""
from flask import Blueprint

main_bp = Blueprint('main', __name__)


def register_bp(app):
    """Register the 'main' blueprint on the current app instance.
    """
    app.register_blueprint(main_bp)
    return app


# pylint: disable=wrong-import-position
from . import views  # noqa: E402, F401
