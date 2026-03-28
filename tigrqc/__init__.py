"""Setup and initialization.
"""
from typing import Any, Mapping

from flask import Flask

from .__about__ import __copyright__, __version__
from .extensions import init_extensions
from .load_blueprints import load_blueprints

__all__ = ['__copyright__', '__version__', 'create_app']


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    """Generate an application instance from the given configuration.

    This will load the application configuration, initialize all extensions,
    and register all blueprints.

    Args:
        config: The configuration to provide the application. Optional.
            If not given ``tigrqc.config`` will retrieve and validate the
            configuration and set sensible defaults.

    Returns:
        Flask: The application instance.
    """
    app = Flask(__name__)

    if config is None:
        app.config.from_object('tigrqc.config')
    else:
        app.config.from_mapping(config)

    init_extensions(app)
    load_blueprints(app)

    return app
