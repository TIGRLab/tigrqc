"""Manages blueprint discovery and registration.

Any importable module in the blueprints folder will be registered as a
blueprint if it exposes a 'register_bp' function.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def load_blueprints(app: Flask) -> Flask:
    """Register all blueprints for the app.

    Blueprints must be stored in the 'blueprints' folder and implement the
    'register_bp' function to be loaded by this function.

    Args:
        app: The application instance that must register blueprints.

    Returns:
        Flask: The application instance.
    """
    # pylint: disable=import-outside-toplevel
    import tigrqc.blueprints as bp_pkg

    for _, name, _ in pkgutil.iter_modules(bp_pkg.__path__):
        module = importlib.import_module(f'{bp_pkg.__name__}.{name}')

        if hasattr(module, 'register_bp'):
            module.register_bp(app)

    return app
