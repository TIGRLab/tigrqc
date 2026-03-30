"""Context processors to inject application-wide template variables.

See the [Flask documentation](
https://flask.palletsprojects.com/en/stable/templating/#context-processors
) for more information.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from flask import current_app

from .__about__ import __copyright__, __version__

if TYPE_CHECKING:
    from flask import Flask

_processors: list[Callable[..., dict[str, Any]]] = []


def context_processor[F: Callable[..., dict[str, Any]]](func: F) -> F:
    """Decorator to register a function as a context processor.
    """
    _processors.append(func)
    return func


@context_processor
def inject_site_settings() -> dict[str, Any]:
    """Add template variables for customizable site settings.
    """
    return {
        'org_brand': current_app.config.get('BRAND'),
        'org_logo': current_app.config.get('LOGO'),
        'org_help': current_app.config.get('HELP_DOCS'),
        'org_support': current_app.config.get('SUPPORT_EMAIL'),
    }


@context_processor
def inject_app_details() -> dict[str, Any]:
    """Add template variables for non-static application details.
    """
    return {
        'copyright': __copyright__,
        'version': __version__,
    }


def register_context_processors(app: Flask) -> None:
    """Register all context processors on the current app instance.

    Args:
        app: The application instance.
    """
    for proc in _processors:
        app.context_processor(proc)
