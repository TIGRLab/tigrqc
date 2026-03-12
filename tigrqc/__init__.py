"""Setup and initialization.
"""
from typing import Any, Mapping

from flask import Flask

from .extensions import init_extensions


def create_app(config: Mapping[str, Any] | None = None) -> Flask:
    """Generate an application instance from the given configuration.

    This will load the application configuration, initialize all extensions,
    and register all blueprints.
    """
    app = Flask(__name__)

    if config is None:
        app.config.from_object('tigrqc.config')
    else:
        app.config.from_mapping(config)

    init_extensions(app)

    return app
