"""A blueprint that provides views to let admins configure global settings.

This includes:
    - User management
    - Configuration of external data sources (XNAT, REDCap)
    - Scan site configuration
"""
from flask import Blueprint

settings_bp = Blueprint(
    'settings',
    __name__,
    template_folder='templates',
    url_prefix='/admin/settings'
)


def register_bp(app):
    """Register the 'settings' blueprint on the current app instance.
    """
    app.register_blueprint(settings_bp)
    return app


# pylint: disable=wrong-import-position
from . import views  # noqa: E402, F401
